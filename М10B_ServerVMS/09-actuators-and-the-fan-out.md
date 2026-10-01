# Урок 9 — Актуаторы и раздача

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `gstvms/actuator.py` — `GstActuator` (строка конвейера с двумя ветвями `tee`, шина, фильтр наблюдений, `pump`, `stop_all`) и `GstRecActuator` (два источника на выбор, `appsink` — каждый кадр сэмплом в писатель тома, кольцо для резервной записи); и `gstvms/livesrv.py` — `FanOut` на `GstRtspServer`.
**Время:** ~100 минут.

## Зачем этот урок

Самый плотный урок модуля: три файла смыкаются здесь в одну работающую систему.

Воркер из урока 4 держит камеру — но чем именно, до сих пор не сказано. Регистратор из урока 10 подписывается на раздачу — но раздачи ещё нет. Элемент из урока 5 написан и ни разу не включён в конвейер, а движок архива из урока 6 ждёт кадров, которые ему никто не отдаёт.

Урок делает три вещи.

**Строка конвейера с `tee` и двумя ветвями.** Одно соединение к камере, размноженное на два пути: RTP на петлевой интерфейс (оттуда его подхватывает RTSP-раздача — для подписчиков где угодно) и разделяемая память (для подписчиков на этой же машине). Обе ветви — `leaky`, и почему именно так, разбирается отдельно.

**Раздача на `GstRtspServer`.** Одна **общая** фабрика на камеру: сколько бы клиентов ни подключилось, конвейер один. Пятьдесят зрителей — один приёмник RTP.

**Актуатор регистратора, отличающийся от воркерского строкой конвейера и стоком.** `GstRecActuator` наследует сборку, шину, `pump` и `stop_all`. Своё у него — `describe` (какую строку собрать) и то, куда уходят кадры: конвейер кончается на `appsink`, и каждый кадр уходит сэмплом в писатель тома. Файлов регистратор не пишет вовсе.

И два решения, которые урок объясняет прямо: **почему раздача — это RTSP, а не multicast**, и **когда она становится разделяемой памятью**.

> **Проверка без железа.** Почти ничего: этот файл написан к биндингу GStreamer и в обычном прогоне не исполняется. Проверяется то, что он зовёт: `resolve`, ворота воркера и сток регистратора — `RecSink` пишет в настоящий `obsd`, кадры ему подаёт поддельный актуатор (урок 10). На коробке — зомби из двух настоящих процессов и `kill -9` посреди записи.

## Что нужно знать заранее

- **Урок 4** — две ветви раздачи и правило «выбирает подписчик».
- **Урок 3** — `FakeActuator` и его три метода: настоящий обязан уложиться в них.
- **Урок 5** — `driverpacksrc`: источник воркерской строки.
- **Урок 6** — [`obsd`](06-objectstorage-the-engine.md): писатель тома, в который регистратор отдаёт кадры; **урок 7** — [последовательность](07-volume-block-sequence-stream.md), которая открывается только на ключевом кадре.
- **М10A, урок 12** — бакеты: куда попадёт то, что элемент объявит на шине.

## Чему вы научитесь

1. Собирать конвейер строкой и понимать, что даёт `parse_launch` вместо ручной сборки.
2. Размножать поток `tee` и делать ветви протекающими, чтобы медленный потребитель не останавливал быстрых.
3. Раздавать один поток многим по RTSP и объяснять, почему не multicast.
4. Превращать сообщения шины в две плоские очереди и отделять служебное от наблюдений.
5. Ловить зависший источник сторожевым таймером.
6. Делать подсистему выбором строки конвейера, а не новым конвейером.
7. Отдавать кадры из конвейера в писатель тома: `appsink`, время съёмки, пропуск до ключевого кадра после отказа.

---

## Шаг 1 — Две роли в одной шапке

```
GstActuator     the WORKER's: `driverpacksrc ! h264parse ! watchdog ! tee`, the tee's branch RTP to the
                loopback port the RTSP fan-out (`livesrv.py`) serves as rtsp://<server>:8554/<cam>. It holds
                the camera and records nothing.
GstRecActuator  the RECORDER's: `rtspsrc location=<live_url> ! rtph264depay ! h264parse ! appsink` —
                subscribed to the fan-out, every access unit a sample into the volume's writer (ObjectStorage,
                through the host's `obsd`) under the recorder's epoch.
```

Решение из урока 4, записанное двумя строками конвейера. В первой **нет стока в том**. Во второй **нет `driverpacksrc`**. Ни один процесс не делает обе вещи.

Обратите внимание на слова «under the recorder's epoch». У регистратора **своя эпоха**, не воркерская. Запись — отдельная единица работы со своим отсечением: воркер может умереть и смениться, не обесценив записанное, и наоборот.

## Шаг 2 — Строка воркера

```python
DESC = ("driverpacksrc name=src ! h264parse ! watchdog timeout={watchdog} ! tee name=t "
        "t. ! queue leaky=downstream max-size-buffers=30 ! {live} "
        "t. ! queue leaky=downstream max-size-buffers=30 ! {shm}")
SHM = "shmsink socket-path={path} shm-size=20000000 wait-for-connection=false sync=false"
LIVE = "rtph264pay config-interval=1 pt=96 ! udpsink host=127.0.0.1 port={port} sync=false"
IDLE = "fakesink sync=false"
```

Разберём по элементам.

`driverpacksrc name=src` — источник из урока 5. **Адреса в шаблоне нет**, и это не забывчивость: строка запуска попадает в лог при ошибке разбора, в крэш-дамп и в вывод `ps`, а у камеры, кроме адреса, есть ещё логин и пароль. Всё трое ставятся свойствами элемента **после** разбора — шаг 6; `name=src` здесь затем, чтобы потом было за что взяться. Почему так, а не «не забывать редактировать в каждом месте, которое печатает строку», — урок 19.

`h264parse` — приводит поток в форму с явными границами кадров. Без него `tee` размножал бы байты, а не кадры, и получатели не смогли бы найти начало.

`watchdog timeout={watchdog}` — восемь секунд по умолчанию, и это **единственный способ узнать, что источник завис**. Камера не закрыла соединение, не выдала ошибку, просто перестала отдавать кадры: с точки зрения конвейера всё в порядке, он ждёт. Сторожевой таймер объявляет ошибку, если за восемь секунд не прошло ни одного буфера, ошибка попадает на шину, шина — в `dead`, `dead` — в `lost` и событие `silent` (урок 4).

**Зависание без сторожевого таймера — самый неприятный вид отказа**: процесс жив, конвейер существует, `phase` показывает `running`, и ничего не происходит. Восемь строк конфигурации превращают это в обычный отказ.

`tee name=t` — точка размножения. Дальше две ветви, каждая начинается с `t.`.

## Шаг 3 — Почему очереди протекают

```
t. ! queue leaky=downstream max-size-buffers=30 ! {live}
t. ! queue leaky=downstream max-size-buffers=30 ! {shm}
```

Самая важная строка конфигурации в файле, и её стоит разобрать до конца.

**`tee` синхронен.** Он отдаёт буфер всем ветвям и **ждёт, пока все примут**. Одна медленная ветвь останавливает весь конвейер — включая чтение с камеры.

Что будет без очередей: подписчик разделяемой памяти подвис на секунду (диск занят, процесс в свопе) — и камера перестала читаться. У всех. Один медленный потребитель роняет держание камеры.

`queue` разрывает эту связь: у каждой ветви свой поток и свой буфер. `tee` отдаёт в очередь и идёт дальше.

Но очередь конечна, и когда она заполнена, всё возвращается к тому же — если только не сказать, что делать при переполнении.

**`leaky=downstream`** — выбрасывать самые старые буферы. И вот почему именно это, а не «блокировать» (по умолчанию) и не «выбрасывать новые»:

Для **живого** потока старый кадр бесполезен. Зритель, отставший на тридцать кадров, не хочет увидеть их все с задержкой — он хочет видеть настоящее. Выбросить старое и показать свежее — правильное поведение для живого видео и неправильное для записи.

Именно поэтому **на пути записи очередь не протекает**: в стоке регистратора (ниже) `appsink` с ограниченной очередью без `drop` — переполненный, он притормаживает конвейер, а не выбрасывает кадры. Запись обязана быть полной, и если писатель не успевает, лучше притормозить конвейер, чем получить архив с дырами. Одно исключение стоит в той же строке и подтверждает правило: кольцо резервной записи на удержании (шаг 9) протекает намеренно, потому что выбрасывать старое — его назначение.

**Разные ветви — разная политика потерь**, и это одно из тех различений, которые определяют, чем система в итоге окажется.

`max-size-buffers=30` — около секунды при 25 кадрах в секунду. Достаточно, чтобы пережить заминку, мало, чтобы накопить задержку.

`sync=false` на обоих стоках: не привязываться к часам конвейера. Темп задан один раз, в `identity sync=true` внутри источника (урок 5); синхронизировать ещё и на выходе значит задерживать дважды.

`wait-for-connection=false` у `shmsink` — **не ждать читателя**. Иначе камера, которую никто не пишет, не запустилась бы вовсе: конвейер встал бы на первом буфере, ожидая, когда кто-нибудь подключится к разделяемой памяти. Держание камеры не зависит от наличия подписчиков — это то же правило, что «воркер держит, а записывает другой».

`shm-size=20000000` — двадцать мегабайт кольцевого буфера, около секунды H.264 в хорошем качестве.

`IDLE = "fakesink sync=false"` — заглушка для ветви, у которой нет адреса. В `describe` видно, когда она используется.

## Шаг 4 — Почему RTSP, а не multicast

Вопрос, который возникает у всякого, кто занимался видео: **раздача одного потока многим — это же ровно то, для чего существует multicast.** Один пакет, коммутатор размножает, подписчики получают. Нулевая нагрузка на источник.

Почему здесь не так.

**Multicast не проходит через маршрутизаторы без настройки.** Нужен PIM, нужен IGMP snooping на коммутаторах, нужны согласованные настройки во всех сегментах. В одной подсети — работает; между стойками, между зданиями, через VPN — требует сетевого проекта, который делается не вами и не сегодня.

**Multicast не проходит в облако.** Ни один из крупных провайдеров его не поддерживает. Система, чья раздача построена на multicast, не переносится в облако вообще.

**Multicast не имеет состояния сессии.** Нельзя узнать, кто подписан; нельзя понять, что последний зритель ушёл; нельзя посчитать ёмкость шлюза в зрителях (урок 13). Всё это строится на том, что подписка — это соединение.

**Multicast не проходит через TCP-only сети.** Комментарий к `livesrv.py` называет это прямо: *TCP-interleaved is allowed, so a VLAN that passes no UDP still gets the stream.* Сеть камер, где UDP заблокирован политикой, — обычное дело в охраняемых объектах.

Что даёт RTSP взамен: работает везде, где работает TCP; имеет сессии; поддерживается всем; и **стоимость размножения ограничена** — подписчиков раздачи единицы (регистратор, шлюз, пара детекторов), а не десятки. Десятки зрителей висят на шлюзе (урок 13), который подписан **один раз**.

Правило, которое из этого выводится: **оптимизация, требующая настройки сети, не является частью системы.** Она может быть, а может не быть, и система должна работать в обоих случаях.

## Шаг 5 — Раздача

```python
FACTORY = "( udpsrc port={port} caps=\"{caps}\" ! rtpjitterbuffer latency=100 ! rtph264depay ! h264parse config-interval=-1 ! rtph264pay name=pay0 pt=96 config-interval=1 )"


class FanOut:
    def __init__(self, port: int = 8554):
        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(port))
        self.mounts = self.server.get_mount_points()
        self.published: dict[str, GstRtspServer.RTSPMediaFactory] = {}
        self.server.attach(None)
        self.loop = GLib.MainLoop()
        import threading
        threading.Thread(target=self.loop.run, daemon=True).start()
```

Один сервер на процесс воркера, порт 8554 (стандартный для RTSP).

**В продукте это отдельный процесс.** В курсе медиастек — DriverPack, конвейер камеры, раздача — живёт в процессе воркера, и так же он жил в продукте до 1 октября 2026. Теперь там хост драйверов `ipintd`: C++-процесс на сервер, юнит ОС; воркер говорит с ним по unix-сокету командами `CAM_START`/`CAM_STOP` и получает события `started`, `dead`, `stopped`, и через воркер не проходит ни одного кадра (обратная связь CM) — та же развилка, что у архива с `obsd` (урок 6). Цикл воркера, эпохи, аренды и heartbeat от этого не меняются: актуатор из шага 6 — тот же шов, за ним другой процесс. Меняются отказы: упавший воркер не роняет камер — хост держит их 15 секунд и отдаёт вернувшемуся процессу того же слота без перезапуска, меняется только эпоха; упавший хост воркер замечает по сокету и объявляет его камеры мёртвыми, когда ОС его поднимет. Пятнадцать секунд — число, которое надо сверять с платформой (урок 4).

`GLib.MainLoop` в **отдельном демоническом потоке**: `GstRtspServer` требует крутящийся главный цикл GLib, а у воркера свой цикл (урок 4), никак с GLib не связанный. Два цикла в одном процессе, каждый в своём потоке.

```python
    def publish(self, name: str, live_port: int) -> None:
        if name in self.published:
            return
        f = GstRtspServer.RTSPMediaFactory()
        f.set_launch(FACTORY.format(port=live_port, caps=RTP_CAPS))
        f.set_shared(True)                                 # one pipeline per camera, N sessions from it
        f.set_protocols(GstRtspServer.RTSPLowerTrans.TCP | GstRtspServer.RTSPLowerTrans.UDP)
        self.mounts.add_factory("/" + name, f)
        self.published[name] = f
```

**`set_shared(True)` — вся суть класса в одной строке.**

Без неё `GstRtspServer` создаёт **конвейер на каждого клиента**. Каждый клиент — свой `udpsrc` на том же порту, и они начинают драться за пакеты: UDP-порт может читать только один.

С ней конвейер **один на камеру**, а клиенты получают сессии от него. Пятьдесят подключений — один `udpsrc`, один разбор, один упаковщик.

`set_protocols(TCP | UDP)` — клиент выбирает. TCP медленнее и надёжнее, проходит через что угодно; UDP быстрее. Разрешены оба, решает подписчик — то же правило, что и с выбором между шм и сетью.

`rtpjitterbuffer latency=100` — сто миллисекунд на упорядочивание. RTP по UDP приходит вразнобой и с потерями; буфер выстраивает и ждёт опоздавших.

`config-interval=-1` у `h264parse` и `=1` у `rtph264pay`: параметры потока (SPS/PPS) вставляются в каждый ключевой кадр и раз в секунду соответственно. Без этого клиент, подключившийся в середине, **не может начать декодирование** — у него нет заголовков. Клиент ждал бы следующего ключевого кадра с параметрами, то есть до бесконечности.

`"/" + name` — путь монтирования: `rtsp://box:8554/7`. То самое, что воркер публикует как `live_url`.

```python
    def unpublish(self, name: str) -> None:
        if self.published.pop(name, None) is not None:
            self.mounts.remove_factory("/" + name)
```

Камера остановлена — монтирование снимается, сессии закрываются. Подписчики получают обрыв и переподписываются (урок 10).

## Шаг 6 — Актуатор: три метода и ни одним больше

```python
class GstActuator:
    """The worker's: holds the camera, serves the fan-out, records nothing."""

    def __init__(self, watchdog_ms: int = 8000, rtsp_port: int = 8554):
        self.watchdog = watchdog_ms
        from .livesrv import FanOut
        self.fanout = FanOut(rtsp_port)
        self.pipelines: dict[int, Gst.Pipeline] = {}
        self.dead: list[int] = []
        self.posted: list[tuple[int, str, dict]] = []
```

**Та же поверхность, что у `FakeActuator`** (урок 3): вызываемый, `pump()`, `stop_all()`. Примечание к модулю формулирует следствие: *воркер не знает, какой из них он держит.*

Это то, ради чего поддельный актуатор был написан первым. Настоящий укладывается в интерфейс, зафиксированный тестами, а не наоборот.

```python
    def __call__(self, verb: str, cam: dict) -> bool:
        cid = cam["id"]
        if verb in ("stop", "restart") and cid in self.pipelines:
            p = self.pipelines.pop(cid)
            p.send_event(Gst.Event.new_eos())            # lets the last access units reach the sink
            p.set_state(Gst.State.NULL)
        if verb == "stop":
            self._unpublish(cid)
            return True
```

**EOS перед `NULL`** — сигнал конвейеру, что поток кончился, чтобы последние кадры дошли до стока. `NULL` без EOS обрывает конвейер мгновенно.

В воркерском конвейере стока в том нет — но `GstRecActuator` наследует этот метод, и там он есть. Регистратор к тому же, прежде чем звать этот метод, закрывает открытую последовательность своего стока (шаг 9). Одна строка обслуживает обоих.

`stop` снимает публикацию раздачи. Камера остановлена — её монтирования быть не должно.

```python
        try:
            p = Gst.parse_launch(self.describe(cam))
            src = p.get_by_name("src")
            src.set_property("uri", cam["source"])                    # the URI, after the parse: see DESC
            if cam.get("cred_username"):
                src.set_property("user", cam["cred_username"])
            if cam.get("cred_secret"):
                src.set_property("password", cam["cred_secret"])
        except Exception as e:                        # noqa: BLE001
            log.error("camera %s: %s", cid, e)        # the message may name the URI; it can no longer name the password
            return False
```

`parse_launch` — сборка конвейера **из строки**. Ручная сборка (создать элементы, добавить, связать, обработать динамические пады) заняла бы тридцать строк вместо одной и была бы нечитаема.

И важный побочный эффект: **строку конвейера можно скопировать в `gst-launch-1.0` и запустить руками.** Отладка видеоконвейера без этой возможности мучительна; с ней — обычная работа.

`except Exception` ловит всё: отказанный URI из урока 5, отсутствующий плагин, синтаксическую ошибку в строке. Логируется, возвращается `False`, цикл сверки уходит в откат.

```python
        bus = p.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", lambda b, m, c=cid: self.dead.append(c))
        bus.connect("message::element", lambda b, m, c=cid: self._posted(c, m))
        if p.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            return False
        self.pipelines[cid] = p
        self._publish(cid, cam)
        return True
```

`c=cid` в лямбдах — связывание значения на момент создания. Без него все лямбды захватили бы одну переменную цикла, и все сообщения приписались бы последней камере. Классическая ловушка замыканий, и здесь она стоила бы часов отладки.

Публикация раздачи — **после** успешного `PLAYING`. Объявлять адрес, по которому ещё ничего нет, не стоит: подписчик подключится и не получит ничего.

## Шаг 7 — Строка через `describe`

```python
    def describe(self, cam: dict) -> str:
        live = LIVE.format(port=cam["live_port"]) if cam.get("live_port") else IDLE
        shm = SHM.format(path=cam["live_shm"][len("shm://"):]) if cam.get("live_shm") else IDLE
        return DESC.format(watchdog=self.watchdog, live=live, shm=shm)
```

Единственный метод, который переопределит регистратор. Всё остальное — общее.

Каждая ветвь либо получает свой сток, либо заменяется на `fakesink`. **Ветвь `tee` нельзя оставить неподключённой**: `tee` заблокируется, ожидая, когда её кто-нибудь заберёт. `fakesink` забирает и выбрасывает.

`cam["live_shm"][len("shm://"):]` — снятие схемы. В heartbeat'е адрес с `shm://` (чтобы подписчик по схеме понял, что это), в `shmsink` — голый путь.

## Шаг 8 — Шина в две очереди

```python
    def _posted(self, cid: int, msg) -> None:
        st = msg.get_structure()
        src = getattr(msg, "src", None)
        factory = src.get_factory() if src is not None and hasattr(src, "get_factory") else None
        if st is None or not observes(factory.get_name() if factory is not None else "", st.get_name()):
            return                                       # plumbing, not an observation
        fields = {}
        for i in range(st.n_fields()):
            name = st.nth_field_name(i)
            v = st.get_value(name)
            if isinstance(v, (int, float, str, bool)):
                fields[name] = v
        self.posted.append((cid, st.get_name(), fields))
```

**Наблюдение — только то, что сказал наш элемент.** Первая версия отбрасывала сообщения по списку имён: `GstBinForwarded` и два сообщения `splitmuxsink`. Список «что выбросить» неверен в тот день, когда у GStreamer появляется новое сообщение. На ящике продукта `rtpbin` слал `application/x-rtp-source-sdes` каждые несколько секунд, и каждое ложилось в журнал событий камеры как событие камеры (обратная связь, BL). Вопрос перевёрнут: не «что это за сообщение», а «кто его послал».

```python
OUR_ELEMENTS = ("driverpacksrc",)
PLUMBING = ("GstBinForwarded",)


def observes(factory: str, name: str, extra: tuple = ()) -> bool:
    ours = OUR_ELEMENTS + tuple(extra) + tuple(f for f in os.environ.get("EVENT_ELEMENTS", "").split(",") if f)
    return factory in ours and name not in PLUMBING
```

Функция лежит в `gstvms/observes.py` и GStreamer не импортирует — поэтому у неё есть тест, которому GStreamer не нужен. Аналитический элемент, добавленный в установке, называют в `EVENT_ELEMENTS`. Сам `_posted` на машине курса не запускался: здесь нет GStreamer, и то, что `msg.src.get_factory()` возвращает ожидаемое имя для элемента на Python, проверено чтением, а не прогоном.

Наш элемент в списке теперь один — `driverpacksrc`. Сток регистратора — не элемент, который что-то объявляет на шине, а `appsink`, отдающий кадры в писатель тома, и наблюдений у него нет. В списке служебного осталось одно имя: `GstBinForwarded`, сообщение GStreamer о собственной работе.

Всё остальное — **наблюдение**, и это открытая дверь. Имя структуры становится видом события (`motion`, `person`, что угодно), скалярные поля копируются как есть.

Правило в докстроке `pump`:

> *The element never knows about buckets or epochs: it posts what it saw; the worker, which holds the epoch, turns it into a line.*

**Элемент аналитики ничего не знает о системе.** Он объявляет на шине структуру с именем и полями — обычная практика GStreamer. Воркер, который держит эпоху, превращает её в строку в бакете (урок 4).

Следствие: **добавить аналитику — значит вставить элемент в ветвь.** Ни регистрации, ни конфигурации, ни правки воркера. Поле `track_id`, добавленное в структуру, окажется на странице в тот же день (урок 19 М10A).

Фильтр по типам (`int, float, str, bool`) отсекает структуры GStreamer, которые не сериализуются в JSON.

```python
    def pump(self) -> tuple[list[int], list[tuple[int, str, dict]]]:
        dead, self.dead = self.dead, []
        posted, self.posted = self.posted, []
        for cid in dead:
            p = self.pipelines.pop(cid, None)
            if p:
                p.set_state(Gst.State.NULL)
        return dead, posted
```

Обмен списков одной строкой — атомарная замена: обратные вызовы шины, сработавшие во время `pump`, попадут уже в новый список, а не потеряются.

Мёртвые конвейеры останавливаются здесь, а не в обратном вызове: обратный вызов шины выполняется в контексте GLib, менять состояние конвейера оттуда — просить о взаимоблокировке.

Примечание к файлу честно отмечает слабое место: *обратные вызовы шины выполняются в главном контексте GLib; поскольку воркер не крутит цикл GLib, доставка `add_signal_watch` зависит от того, что контекст по умолчанию итерируется.* Здесь это работает благодаря циклу, запущенному раздачей, — и это то место, которое стоит знать, если сообщения вдруг перестанут приходить.

## Шаг 9 — Регистратор: строка, которая кончается на `appsink`

Сток регистратора — не файл. Урок 10 отдаёт актуатору в строке записи готовый объект — `RecSink`, писателя тома под именем и эпохой этой записи, — и актуатор кладёт в него каждый кадр:

```python
# The recorder's sink is not a file: every access unit leaves the pipeline through `appsink` and goes into the
# volume's writer as one sample (`RecSink`, `vms/recworker.py`) — byte-stream, one access unit per buffer, the
# parameter sets on every key frame (`config-interval=-1`), so a sequence the engine opens on a key frame can be
# played on its own.
REC_SINK = ("h264parse config-interval=-1 ! video/x-h264,stream-format=byte-stream,alignment=au ! "
            "watchdog timeout={watchdog} ! {ring}appsink name=sink emit-signals=true sync=false max-buffers=200")
# The prebuffer of a `when: offline` backup (Lesson 26): a queue that holds the last N seconds and drops the
# oldest when full — `leaky=downstream` — with its source pad blocked while the backup is on hold. Released,
# it pushes what it holds into the sink first. After the watchdog, so a held pipeline is still watched.
RING = "queue name=ring max-size-time={ring_ns} max-size-buffers=0 max-size-bytes=0 leaky=downstream ! "
REC_DESC = "rtspsrc location={source} latency=200 protocols=tcp name=src ! rtph264depay ! " + REC_SINK       # another server's worker: its fan-out
…
REC_SHM_DESC = "shmsrc socket-path={path} is-live=true do-timestamp=true name=src ! video/x-h264,stream-format=byte-stream ! " + REC_SINK   # this server's worker: its tee, directly
```

Разберём `REC_SINK` по элементам.

`alignment=au` — **один буфер на кадр** (access unit). Писатель тома принимает сэмплы, и сэмпл движка — это кадр со своим началом, концом и признаком ключевого. Без выравнивания `appsink` отдавал бы куски потока, и границу кадра пришлось бы искать в стоке самим.

`config-interval=-1` у `h264parse` — параметры потока (SPS/PPS) **в каждом ключевом кадре**. Движок режет запись на последовательности, и каждая открывается ключевым кадром (урок 7). Последовательность с параметрами внутри играется сама по себе: читатель может начать с любой, не ища заголовки где-то раньше.

`watchdog` — тот же сторож, что у воркера, и по той же причине: подписка, переставшая отдавать кадры, — это `running` без записи, пока его нет.

`appsink name=sink emit-signals=true` — **выход из конвейера в Python**: на каждый буфер `appsink` подаёт сигнал `new-sample`, и обработчик забирает кадр. `sync=false` — по той же причине, что у стоков воркера: темп задан источником. `max-buffers=200` — очередь перед обработчиком конечна и без `drop`: если писатель не успевает, конвейер притормаживает, а не выбрасывает (шаг 3).

`{ring}` — пусто для обычной записи и кольцо `RING` для резервной записи с `when: offline`. О нём ниже.

**Строки источника не изменились.** `protocols=tcp` у `rtspsrc` — для записи только TCP: запись не терпит потерь, а UDP теряет, лишняя задержка записи безразлична. `latency=200` — вдвое больше, чем у раздачи (100 мс), по той же причине: полнота важнее задержки. `stream-format=byte-stream` у `shmsrc` — разделяемая память отдаёт голые байты без описания формата, и его надо назвать явно.

### Класс

```python
class GstRecActuator(GstActuator):
    """The recorder's: `rtspsrc` on the camera's fan-out URL — or `shmsrc` on the worker's shared-memory
    branch when the worker is on this server — then `appsink`, each access unit a sample into the volume's
    writer under the recorder's epoch. No fan-out of its own; nothing here reads a camera."""

    def __init__(self, watchdog_ms: int = 8000):
        self.watchdog = watchdog_ms
        self.fanout = None
        self.range_error = ""                            # why the last range pipeline failed, if it did (Lesson 16)
        self.pipelines, self.dead, self.posted = {}, [], []

    # `release` opens a held pipeline's ring; every other verb is the worker's.
    def __call__(self, verb: str, cam: dict) -> bool:
        if verb == "release":
            return self._release(cam["id"])
        if verb in ("stop", "restart") and cam["id"] in getattr(self, "sinks", {}):
            # The open sequence closed: what was taken is kept — and a restart (back on hold, a new source) must not
            # let the next frames continue it after a gap: a hole inside a sequence is drawn as footage.
            sink = self.sinks.pop(cam["id"])
            ok = super().__call__(verb, cam)              # the pipeline down first…
            sink.finish()                                 # …then the sequence closed: nothing arrives after this
            return ok
        return super().__call__(verb, cam)
```

Порядок — сначала конвейер в `NULL`, потом `finish` — не случаен: ключевой кадр, пришедший в сток между `finish` и `NULL`, открыл бы последовательность, которую никто не закроет (ревью платформы, B4, в его форме для `obsd`).

**Конструктору больше нечего знать.** Ни каталога спула, ни архива, ни длины сегмента: куда писать, приходит в строке записи (`cam["sink"]`) от регистратора, который держит том. Актуатор не знает, какой это том и открыт ли он; знает регистратор (урок 10, шаги 6 и 8).

`self.fanout = None` — у регистратора нет своей раздачи. Он подписчик, не источник; `_publish` и `_unpublish` в базовом классе проверяют `None` и ничего не делают.

`stop` и `restart` **сначала закрывают открытую последовательность** стока (`finish`), и только потом зовут воркерский глагол с его EOS и `NULL`. Комментарий называет две причины. Первая — для `stop`: взятое движком остаётся на томе. Вторая — для `restart`: конвейер возвращается на удержание или меняет источник, и между последним кадром до перезапуска и первым после проходит время. Продолжи новые кадры ту же последовательность, дыра оказалась бы внутри неё, а таймлайн рисует последовательность как запись без разрывов.

`release` — глагол, которого у воркера нет: открыть кольцо резервной записи. Регистратор зовёт его, когда основная запись пропала (урок 26).

### Каждый кадр — в писатель

Сток подключается до запуска, в `_before_play` — крючке, который базовый `__call__` зовёт между сборкой и `PLAYING`:

```python
    def _before_play(self, p, cam: dict) -> None:
        import time as _time
        from w2cplatform.obsd import ObsdError, archive_ms, video
        sink = p.get_by_name("sink")
        if sink is not None and cam.get("sink") is not None:
            self.offered_bytes = getattr(self, "offered_bytes", {})
            self.offered_bytes.setdefault(cam["id"], 0)
            self.sinks = getattr(self, "sinks", {})
            self.sinks[cam["id"]] = writer = cam["sink"]
            skipping = {"until_key": False}

            def on_sample(appsink, cid=cam["id"]):
                smp = appsink.emit("pull-sample")
                buf = smp.get_buffer()
                data = buf.extract_dup(0, buf.get_size())
                self.offered_bytes[cid] += len(data)
                key = not buf.has_flags(Gst.BufferFlags.DELTA_UNIT)
                clock = p.get_clock()
                running = (clock.get_time() - p.get_base_time()) if clock is not None else 0
                ago = max(0, running - buf.pts) / Gst.SECOND if buf.pts != Gst.CLOCK_TIME_NONE else 0.0
                begin = _time.time() - ago
                dur = buf.duration / Gst.SECOND if buf.duration != Gst.CLOCK_TIME_NONE else 0.04
                if skipping["until_key"] and not key:
                    return Gst.FlowReturn.OK
                try:
                    writer.put(video(archive_ms(begin), archive_ms(begin + dur), data, key))
                    skipping["until_key"] = False
                except ObsdError:
                    skipping["until_key"] = True          # refused: the rest of this group is lost, the next key opens anew
                return Gst.FlowReturn.OK

            sink.connect("new-sample", on_sample)
        …
```

Четыре решения в двадцати строках.

**Отданное считается здесь, до писателя.** `offered_bytes` растёт на каждый кадр, который конвейер довёл до стока, взял его движок или нет. Это половина сравнения, которое делает сторож писателя (урок 10, шаг 12): «отдано» против «дошло до кольца». Считать после `put` значило бы мерить то, что движок взял, — то есть ровно то, в чём сторож и сомневается. Метод `offered(cid)` отдаёт число регистратору; актуатор, который его не умеет, не говорит ничего, и молчание читается как «не измерено».

**Время кадра — время съёмки, а не время прихода.** Метка буфера (`pts`) — время в конвейере. Обработчик переводит её в настенные часы: сейчас минус то, насколько кадр отстал от часов конвейера. Для живой записи разница — доли секунды. Для кольца резервной записи — до тридцати секунд, и без этого перевода кольцо, выпущенное в момент пропажи основной, легло бы в том «сейчас», а не туда, где оно снято. Время движка — миллисекунды с 1900 года (`archive_ms`, урок 6).

**Отказ — и пропуск до ключевого кадра.** Писатель, который не взял кадр, бросает `ObsdError` — в том числе `Unavailable`, когда пропал демон; `RecSink` перед этим сам сообщает регистратору, что случилось (урок 10, шаг 8). Остаток группы кадров после отказа бесполезен: последовательность открывается только на ключевом кадре. Поэтому обработчик молча пропускает всё до следующего ключевого и пробует снова. Конвейер при этом не останавливается — отказ одного кадра не повод ронять подписку.

**`Gst.FlowReturn.OK` всегда.** Обработчик никогда не говорит конвейеру «ошибка». Что запись не идёт, регистратор узнаёт из своих источников: сток сказал `on_lost` или `on_wrong`, сторож писателя увидел разницу. Ошибка потока в GStreamer означала бы мёртвый конвейер, перезапуск и новую эпоху — за отказ, который через секунду может пройти сам.

### Кольцо резервной записи

Резервная запись с `when: offline` (урок 26) работает **на удержании**: конвейер поднят, подписан и держит последние `ring_seconds` в памяти, ничего не записывая. Кольцо — очередь `RING` перед `appsink`, ограниченная временем, а не числом буферов, и протекающая (`leaky=downstream`): заполненная, она выбрасывает самое старое. Её выход заблокирован пробой, поставленной до `PLAYING`:

```python
        if cam.get("hold"):
            pad = p.get_by_name("ring").get_static_pad("src")
            self.blocks = getattr(self, "blocks", {})
            self.blocks[cam["id"]] = pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, lambda *_: Gst.PadProbeReturn.OK)
```

До запуска, потому что иначе первый буфер успел бы проскочить в сток конвейера, который стартует на удержании. Кольцо стоит после `watchdog`, поэтому удержанный конвейер по-прежнему под присмотром сторожа.

```python
    # Unblock — and drop what the ring pushes until its first KEYFRAME: the leaky queue dropped its oldest
    # buffers one at a time, so it may begin mid-GOP, and the engine opens a sequence only on a key frame. The
    # product measured the result on a box: recording began 28.5 s before the hold was lifted.
    def _release(self, cid) -> bool:
        …
        def to_keyframe(pad_, info):
            if info.get_buffer().has_flags(Gst.BufferFlags.DELTA_UNIT):
                return Gst.PadProbeReturn.DROP
            return Gst.PadProbeReturn.REMOVE

        pad.add_probe(Gst.PadProbeType.BUFFER, to_keyframe)
        pad.remove_probe(probe)
        return True
```

Протекающая очередь выбрасывает старое по одному буферу, поэтому кольцо может начинаться с середины группы кадров. Отдай его писателю как есть — и первые кадры получат отказ до ближайшего ключевого. Проба сама выбрасывает всё до первого ключевого кадра и снимает себя. Дальше кадры идут в писатель тем же `on_sample` — со временем съёмки, то есть на полминуты назад. На ящике продукта запись началась за 28,5 секунды до того, как удержание сняли.

### Диапазон с карты устройства

Ещё одна строка — для дозаписи (урок 16): диапазон с двери воспроизведения устройства, по HTTP.

```python
REC_RANGE_DESC = ("souphttpsrc location={source} ! qtdemux ! h264parse config-interval=-1 ! "
                  "video/x-h264,stream-format=byte-stream,alignment=au ! appsink name=sink emit-signals=true sync=false")
```

Те же `alignment=au` и `config-interval=-1`, тот же `appsink` — но `record_range` не пишет в том сам. Он собирает кадры списком, со временем начала диапазона плюс метка буфера, и возвращает его регистратору; тот кладёт их в поток дозаписи и отбрасывает группы, которые живая запись успела записать раньше (`RecWorker._land`). У конвейера есть срок: длина диапазона плюс минута, не меньше пяти минут. Устройство, переставшее отвечать посреди диапазона, иначе держало бы вызов, сколько захочет TCP.

### Выбор строки

```python
    # The ring is in the pipeline only for a backup that may be held.
    def describe(self, cam: dict) -> str:
        ring = cam.get("ring_seconds")
        kw = dict(watchdog=self.watchdog, ring=RING.format(ring_ns=int(float(ring) * Gst.SECOND)) if ring else "")
        if cam["source"].startswith("shm://"):                                 # the worker is on this server: read its tee's shared memory
            return REC_SHM_DESC.format(path=cam["source"][len("shm://"):], **kw)
        return REC_DESC.format(source=cam["source"], **kw)
```

**Выбор источника по схеме.** `shm://` — воркер на этой же машине, читаем его разделяемую память напрямую. Иначе — `rtspsrc` на адрес раздачи.

Ровно то правило из урока 4: *выбирает подписчик.* И выбор сводится к одной проверке префикса, потому что воркер опубликовал оба адреса и не пытался решать за других.

Заметьте, чего в строке **больше нет**: эпохи. Раньше она стояла свойством элемента записи и решала, в какой каталог лягут сегменты. Теперь эпоха — в имени потока, и её знает сток: `RecSink(lambda: self.store, unit, epoch)`, собранный регистратором из эпох *этого* процесса (урок 10, шаг 6). Видео ляжет в поток `<запись>/e<эпоха регистратора>`, и с эпохой воркера это никак не связано.

## Результат

Воркер, камера 7, сервер `box-a`:

```
driverpacksrc name=src ! h264parse ! watchdog timeout=8000 ! tee name=t
  t. ! queue leaky=downstream max-size-buffers=30 ! rtph264pay config-interval=1 pt=96 ! udpsink host=127.0.0.1 port=20007 sync=false
  t. ! queue leaky=downstream max-size-buffers=30 ! shmsink socket-path=/run/vms/7.shm shm-size=20000000 wait-for-connection=false sync=false
```

Раздача: `rtsp://box-a:8554/7`, одна общая фабрика над портом 20007. Адреса камеры в этой строке нет — он уже стоит свойством `uri` у элемента `src`; чтобы прогнать её руками, `uri` дописывают в `gst-launch-1.0` (урок 5 так и делает).

Регистратор **на том же сервере**:

```
shmsrc socket-path=/run/vms/7.shm is-live=true do-timestamp=true name=src ! video/x-h264,stream-format=byte-stream
  ! h264parse config-interval=-1 ! video/x-h264,stream-format=byte-stream,alignment=au
  ! watchdog timeout=8000 ! appsink name=sink emit-signals=true sync=false max-buffers=200
```

Регистратор **на другом**:

```
rtspsrc location=rtsp://box-a:8554/7 latency=200 protocols=tcp name=src ! rtph264depay
  ! h264parse config-interval=-1 ! video/x-h264,stream-format=byte-stream,alignment=au
  ! watchdog timeout=8000 ! appsink name=sink emit-signals=true sync=false max-buffers=200
```

Резервная запись на удержании, тридцать секунд в памяти — то же, и перед `appsink` кольцо:

```
  ! watchdog timeout=8000 ! queue name=ring max-size-time=30000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream
  ! appsink name=sink emit-signals=true sync=false max-buffers=200
```

Одна камера, одно соединение, две ветви, два возможных подписчика. Каждую из этих строк можно скопировать в `gst-launch-1.0` — у регистраторских, правда, на выходе `appsink`, и руками её стоит заменить на `fakesink`: кадры забирает только регистратор.

## Что может пойти не так

- **`tee` без очередей.** Один медленный подписчик останавливает чтение камеры для всех.
- **`leaky` на пути записи.** Архив с дырами вместо притормозившего конвейера, и заметят это при просмотре инцидента.
- **Ветвь `tee` без стока.** Конвейер заблокируется на первом буфере.
- **`wait-for-connection=true` у `shmsink`.** Камера, которую никто не пишет, не запустится вовсе.
- **`set_shared(False)` у фабрики.** Конвейер на каждого клиента, и все дерутся за один UDP-порт.
- **Multicast вместо RTSP.** Работает в одной подсети, не работает между стойками, в облаке и в TCP-only сети — и посчитать подписчиков нечем.
- **`config-interval` по умолчанию.** Клиент, подключившийся в середине, никогда не начнёт декодировать; последовательность в томе не сыграется сама по себе.
- **`appsink` без `alignment=au`.** Сток получает куски потока вместо кадров, и сэмпл движка не из чего собрать.
- **Время кадра по часам прихода.** Кольцо резервной записи ляжет в том на полминуты позже, чем снято.
- **Писать после отказа, не дожидаясь ключевого кадра.** Каждый следующий кадр группы получит тот же отказ.
- **Ошибка потока из обработчика `appsink`.** Один отказанный кадр роняет конвейер, а перезапуск — это новая эпоха.
- **Кольцо без блокировки до `PLAYING`.** Первые буферы удержанной записи проскочат в том.
- **`cid` без связывания в лямбде.** Все сообщения припишутся последней камере.
- **`NULL` без EOS.** Последние кадры не дойдут до стока.
- **Публикация раздачи до `PLAYING`.** Подписчик подключится к адресу, за которым пусто.
- **Остановка мёртвого конвейера прямо в обратном вызове шины.** Взаимоблокировка в контексте GLib.
- **Конвейер без `watchdog`.** Зависший источник останется `running` навсегда.

## Итог

- Строка воркера кончается на `tee`: стока в том в ней нет, потому что воркер не пишет.
- Очереди на ветвях разрывают синхронность `tee`; `leaky=downstream` для живого, непротекающая для записи — разные ветви, разная политика потерь.
- Раздача — RTSP, а не multicast: multicast требует настройки сети, не идёт в облако, не даёт сессий и не проходит там, где нет UDP.
- Одна общая фабрика на камеру: N клиентов, один конвейер, один приёмник RTP.
- `parse_launch` из строки — и ту же строку можно запустить в `gst-launch-1.0`, дописав адрес. Ни адреса, ни учётных данных в самой строке нет: их ставят свойствами после разбора, потому что строка запуска попадает в лог, в крэш-дамп и в `ps` (урок 19).
- Шина разбирается в две очереди; служебное отфильтровано, остальное — наблюдение, и элемент аналитики ничего не знает ни об эпохах, ни о бакетах.
- Сторожевой таймер превращает зависание — худший вид отказа — в обычную ошибку.
- Регистратор отличается от воркера строкой и стоком: конвейер кончается на `appsink`, каждый кадр уходит сэмплом в писатель тома, со временем съёмки; после отказа сток ждёт ключевого кадра; источник выбирается по схеме адреса, и выбирает подписчик.
- Резервная запись держит последние секунды в протекающем кольце перед стоком и выпускает его с ключевого кадра.

## Упражнения

1. Уберите `queue` с обеих ветвей. Притормозите подписчика разделяемой памяти на секунду (`kill -STOP`) и посмотрите, что стало с чтением камеры.
2. Добавьте `leaky=downstream` перед `appsink` в `REC_SINK`. Притормозите демон (`kill -STOP` процесса `obsd`) на минуту и прочитайте таймлайн записи.
3. Уберите одну ветвь `tee`, не поставив `fakesink`. Запустите конвейер и опишите, где он встанет.
4. Поставьте `wait-for-connection=true`. Создайте камеру без записи и посмотрите, поднимется ли она.
5. Снимите `set_shared(True)`. Подключитесь к раздаче двумя клиентами и найдите, кто из них получает поток.
6. Уберите `config-interval` у `rtph264pay`. Подключитесь через тридцать секунд после старта и засеките, когда появится картинка.
7. Уберите `c=cid` из лямбд. Поднимите три камеры, уроните вторую и скажите, какую из них воркер сочтёт мёртвой.
8. Замените EOS на прямой `NULL` и уберите `finish` из `GstRecActuator.__call__`. Остановите запись штатно и сравните таймлайн с тем, что отдавал конвейер.
9. Уберите `watchdog`. Замените источник на такой, который перестаёт отдавать кадры через минуту, и посмотрите на `phase` через час.
10. Опишите, что понадобится для multicast-раздачи между двумя стойками: какие протоколы, на каком оборудовании, кто это настраивает.
11. Берите время кадра как `time.time()` в момент `new-sample`. Снимите удержание резервной записи и найдите на таймлайне, где легло кольцо.
12. Уберите `skipping`. Отзовите у тома права посреди группы кадров и посчитайте, сколько отказов придёт до следующего ключевого.

## Что дальше

Всё написано: воркер держит, раздача раздаёт, движок архива принимает сэмплы, актуатор регистратора готов. Нет только самого регистратора.

[**Урок 10**](10-recworker.md) пишет `rec.subsystem.yaml` и `RecWorker` — четвёртую подсистему и единственную с настоящим домом: `source` из чужого heartbeat'а, переподписка при переезде держателя, том и его писатель — открыть, держать, открыть заново. Один урок на подсистему — вместо четырёх, которые стоила первая.
