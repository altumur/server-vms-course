# Change 0133-cases-plain-markup

change: 0133-cases-plain-markup rev 1 · lessons Platform/common,P/01–P/05 · author spec103 · state review

Publication parent `23afc4dec9366b2d9991e31ddc64ccd19b696b55`. Step P01.14.4 (ADR-0133 step 6): literal HTML comments in the judge-only `*.cases.md` files become plain headings, so the full check of main reports no unsupported raw HTML. In the P/05 case file `scenario41` gets a space, so EN and RU agree. Case text, tables and numbers are unchanged. No check or `stages.kit.tsv` is changed.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/ru/spec/01.1-store.n5.cases.md` | MODIFIED | 992416bd16e177529ca3521c0777ff806b652e66 | 56aca007a3cd1be02a73f367e01f45aff995f814 | 4a1de054ed3fbf55058f68f8f134ccf343caa9e62c67520c73cebbe21a867e7c |
| `Platform/01-store/ru/spec/01.2-store.n5.cases.md` | MODIFIED | 88305fb957076a6bd6185663e5c51a5f4c862644 | 23aff3ea323bc4719b1561242de015bedbc76d83 | d3ce2d4627520f3676882e9ea0d1ecab5a0a50fe2e27517563d5122f071e7b10 |
| `Platform/01-store/ru/spec/01.3-store.n5.cases.md` | MODIFIED | 1faaad6f015aaf6d635d5e6623a125ab5cda15e4 | 5fd04cbaa6b942639dd55f7977fa90e9300b6f50 | ac17fc152250f9103716c989a941b8980760a8d990e2f5dae3ea4e7125e8d0ed |
| `Platform/01-store/spec/01.1-store.n5.cases.md` | MODIFIED | 59acb5382ee614cccd3d9357b61846ed06c1747a | 1fd89e2c3320b7fe7f1842f0e3530b234e979c62 | 2b87cfc12bb5b9a6ab1096a4314f07acfc750d6bd4c670158f8b93f94bff1819 |
| `Platform/01-store/spec/01.2-store.n5.cases.md` | MODIFIED | 8ccebde2106b6b9b28548752727ee6e185b3f0ae | 881950c21b6a763e48d256067398f0cae8078221 | 60c83103e3e8fc53ad5f6ec34fb43e423a7447343567670eb8b41350c01747c2 |
| `Platform/01-store/spec/01.3-store.n5.cases.md` | MODIFIED | c4f2fd7fe221bd45d31cfa2891872e344454fef3 | 63b82bb3b2ebddd05016f21865d34778530905dc | 2996ece639d57dabe16aeec7058af989538a5fb052f5ce703c70c2a1fddde836 |
| `Platform/02-installer/acceptance/2/README.cases.md` | MODIFIED | 47740c8f77ca4b7940551a41e84e1ec5d8f59e90 | 7f90dfa5f47208025ae9b1c4dd32ee938796b22a | 63e1a5ce827c01384e59eb149358ef676cd6c62837784f608b9783b26b0d29dc |
| `Platform/02-installer/acceptance/3/README.cases.md` | MODIFIED | 47c4bcb755de0a576f0f3a5c40d43e8754651560 | f1793ce0547e244a97049cb32b1c14d9f1b77387 | 5686990948cd2ca0adb2221197780d292577526486f6fd18aecf38aed38ae2c5 |
| `Platform/02-installer/acceptance/4/README.cases.md` | MODIFIED | 9ffc507e3cc670927219305a309f64dae9224338 | aa5599efdf122d68bad1d4d96d76fa86ba40755a | 6fdebd608196964248153802ab252a348fceb1ad068807406030199151a143ac |
| `Platform/02-installer/acceptance/5/README.cases.md` | MODIFIED | 715b93e1887cb1993473eed6578748a6a7acc07c | 659b0db2eaff0e4404c659aec920bbfe53c14687 | e1aecbbf8750651f19b467ae47381f1f506bcd468bc281fbc07469484d6fb4bb |
| `Platform/02-installer/forms/README.cases.md` | MODIFIED | bc2d5c5aab10ce60dbe1ec0332ec703b29f25f51 | 7cc6561084bcb3d71a5c2c26f59ce1094d563dcc | dc55b9f30438878bfd831eccc894c3fa8d4a75df2c15be3cde09dbd3bbcffe62 |
| `Platform/02-installer/ru/acceptance/2/README.cases.md` | MODIFIED | 5fd732fc468eaeb9bfb6bf26ba81637269ab053d | abd07569681a3320b81f59671f49de18c82b8c35 | 778771584a30c978f454fa8b66673b4b6cf557917def5c535e3dc507c6b822a1 |
| `Platform/02-installer/ru/acceptance/3/README.cases.md` | MODIFIED | 9103d47c2bc5dcd72982a400f5f469138ed0d245 | 9b3b36657874734a96473e981a32c2fd84d2855d | a559cfad90d7722299995fc66ed476739fec8cc465994bb8541e3919ee4a1742 |
| `Platform/02-installer/ru/acceptance/4/README.cases.md` | MODIFIED | cda91a08d30256faa973ba4b760946ab066bb6f0 | b06d2965c6833ea7febd4fb8b3e694bc6d9504d5 | 9c95027dbbcd861edcdf2c43c3d90a37769a36688b414cd204a703ba79259b2d |
| `Platform/02-installer/ru/acceptance/5/README.cases.md` | MODIFIED | 715cc353273535fff6461403ab359afb5549c922 | 19f49e223f1cec267c96877f71e6e617fcbd60e1 | c396e78a0d065e37157ed5e3bc544ce1cd8ca668f0548067e34b9b0f4cd850fb |
| `Platform/02-installer/ru/forms/README.cases.md` | MODIFIED | 15c8c28a1b73db279959c8178872575c4b2a3138 | d5457b5e47a4cfa5be783ec83f218ecf2851ff2e | e3cb4ad53c21c5466b0db401c04de557773a684483f036b52da84d3a0f67c79a |
| `Platform/02-installer/ru/spec/02.1-installer.n5.cases.md` | MODIFIED | 95a05b58422523db0e92af664d55cb8ff89651f7 | 67c1f77bbb38f9f662dcefa2139f7b665926a6ae | ff4b151cb927a3c101ebb23ee6487b6b69dd5f2f114067ecfbd39b34768f7a18 |
| `Platform/02-installer/ru/spec/02.3-installer.n5.cases.md` | MODIFIED | 40ee4c844419e2b2e2ded158766e94474f18edbd | cc962fb3065998fda9ffde74d18f22f8b001fa2b | e56f6b4d98e1ff949e135520dff5a707a8160f5a00d85244e6dc58032a218deb |
| `Platform/02-installer/ru/spec/02.5-installer.n5.cases.md` | MODIFIED | 9e33064bb689909ba2dffc66e9033a61f0227ae5 | fccba88db089f12621dca59cea2000c0c45d5d08 | 15f0d133fb2f758876025edf640d0050287b3483c4ef312022abf623b4c773f6 |
| `Platform/02-installer/spec/02.1-installer.n5.cases.md` | MODIFIED | e34024ff0b96bba7b2e2b7ece7debf88da4da4e2 | 46890f490cc1f7a241500d55fd1822e62bfa79e4 | df8ee10d0caedb967121269073b5d7a3dd47c739b0d45ee7d5e8ff539d87da88 |
| `Platform/02-installer/spec/02.3-installer.n5.cases.md` | MODIFIED | 3c37457cbe32818a8faab7460a0e603c90842cde | c0c6f8a20510b6cdab5069d5d5ed21dfa95d5696 | d40c15ab703fd6d4898efb0d7eba990feadb777fd4e8eedb7ab48b2e82ed5ff1 |
| `Platform/02-installer/spec/02.5-installer.n5.cases.md` | MODIFIED | 29596212de5a181ba629a89cd6ec6050d68a834c | c2ce30947301c9f872e239a89df461429c9aaef3 | 1e9c8dd46e58fae09d00e270c8920e63e15dcf134b24d42d36e7b3aef9536a2d |
| `Platform/03-worker/forms/README.cases.md` | MODIFIED | 319aff107d6cac9c2559a18ddf0f5a44e6fca27d | d9dc44f6449800a242c7b51e2d6067c117f22e24 | c6574cda6787e0876fc414a739d360d27b0042f773b392d726a3fffda3a373e3 |
| `Platform/03-worker/ru/forms/README.cases.md` | MODIFIED | 3427568ac4910b243fa8326209ac6677f44e0e33 | a2b1d2a571fae094e06825ae46490b0bc5bf7e8b | d9f7de739424ada81f25135cc2476678173003e034d57e79ac818395e5e0068f |
| `Platform/03-worker/ru/spec/03.2-worker.n5.cases.md` | MODIFIED | 71a3dd0aecdbf92686e79b985f8603160a1bb6ff | b12829bd944fbef60a750a739c3f891493ab6e8d | dcb3bf75fc1ebf24bb86dd714aeb230f771ac14f2d964daf55c0842fc827f478 |
| `Platform/03-worker/ru/spec/03.3-worker.n5.cases.md` | MODIFIED | 3ea15b410c36d88beade5c529c33258e89963f4b | 97dfb21b8b23d0c14cba35f131c7e3599085cb45 | eeef18ff8e19ceb46d333fd293a9fe715d570082ed7ba63b2e0bd2838487bf13 |
| `Platform/03-worker/ru/spec/03.4-worker.n5.cases.md` | MODIFIED | 1ba64708c6104100863275b70b7cb093cf5b0330 | ea1b53957f7a5eb9a9f56bce7207620f33e1b66e | bdbd2d160045f162cfc351b3faeca57d9ee9dc88ae804a3e721758e24d5a5709 |
| `Platform/03-worker/ru/spec/03.6-worker.n5.cases.md` | MODIFIED | 47a5e06abf9731db4f01fac1078e9c9f72b07ddc | 30eda483fabde0e52d12df477d68fc67f24d078c | 029f108c4fdd9e3f1909b4dad826e03da899eb5815078290f45117bc4ae3eacc |
| `Platform/03-worker/spec/03.2-worker.n5.cases.md` | MODIFIED | c1ad8b3936df93434fd5b1b12c9701861f8b210f | aac6d74b6c4006e7c9c7d0808857169c67f16145 | 5404517fb4d662f500c1f943f2a746732c22a84d6b55a67323255a3233f808c7 |
| `Platform/03-worker/spec/03.3-worker.n5.cases.md` | MODIFIED | bce5873cd4229cd1778caa8cab70b415b03d18ab | d7f297e9f69b9d648e395933e440c4b5b873b59f | 9ce6a1ce1944c02c015879ea93c7045eff9ab6eeec90ee33aaf7407b2bde0ee5 |
| `Platform/03-worker/spec/03.4-worker.n5.cases.md` | MODIFIED | d10f0c10d5eb88c781afb94aa910e7796166c221 | 7b8bfb52c5b63fd35c49761e9af8c58e9aa84389 | 3cb96819f4f990130c45d16dedd8a0b93a009a646dfb920d9f21ca9deef2f35e |
| `Platform/03-worker/spec/03.6-worker.n5.cases.md` | MODIFIED | 893da1dcb5eb70c666054b97c9e0d79d22b43028 | 7fa96c46cbf49ee229040d53dd8e2ae1b56281e7 | 5fbe1d46e275dfd8722806247548f9b628b33977f9320e8ca81545217b643ac0 |
| `Platform/04-controller/ru/spec/04-controller.n5.cases.md` | MODIFIED | 5792640ba1f8a5c570d624acbd0f1205c2e679c8 | 6c9019446eab9a27f93dd1bfcf1353c460d8c376 | 0fca4d1ec8e5ab2f911e4b8abf08ba735740728bde375bdb5b68b312059eba70 |
| `Platform/04-controller/ru/vectors/order/README.cases.md` | MODIFIED | 6c007bb21b941c114262364f12f877db234e151e | 8669719ba0c99e090a2b76e564247e0176500652 | f831376e7bdd99f127c83db2ab3a47e71cdd73a0d0752d3440f7022ad1d6ce8c |
| `Platform/04-controller/ru/vectors/shrink-allowed/README.cases.md` | MODIFIED | c9ef21a9ad6f3d94c6b49eed14c3d40e433fa14a | 81c7a9284ef9566c8381fc7ea6ff8308e5ae3bd6 | 87e7d0f98a09516da655eb6d4a785d66f52c75ca01efa357fc95032d9b9aa774 |
| `Platform/04-controller/ru/vectors/shrink-victim/README.cases.md` | MODIFIED | 558e9bd1d689b03cc739ca5d6ec71c00388c6a33 | 5698400418a462101b078916533cf68bdaf05b03 | 2daf1f1e7eda22526ed8f904b81c1494f4507e66e6f26cfbbc0641e4d72c9b23 |
| `Platform/04-controller/spec/04-controller.n5.cases.md` | MODIFIED | 4b4f72a61dda0f86276281ff7c027e3c5080d208 | ca55f8c84140d4713613b7e47b4c940c179ff300 | 47a8af27abbcd8155984f45518fe0ab5ff73e8d8dc7f3dc74b1cffdb1729572f |
| `Platform/04-controller/vectors/order/README.cases.md` | MODIFIED | be2658216b7a9da4c973e424bc8a4003243d48c6 | 2dd410f555839ebcac0a808907a220c7951ddaef | 9b1c1a9e2b98ed66b2a8c0dc17fd75fdc67545f839dadd7e6e5e52f8c227484c |
| `Platform/04-controller/vectors/shrink-allowed/README.cases.md` | MODIFIED | 4e51585acb39250033663fc2008a2e136d1d470d | bea91110dde529e53396506a50ecfc571ea9c7c2 | 9dd8708e6a11791b007595638b56535ca77a6461c04ad4aa7ac9c266091c2623 |
| `Platform/04-controller/vectors/shrink-victim/README.cases.md` | MODIFIED | 35dcb46e2907c444192f2c5b7383eaf33e8c9117 | 173f7bc7556cd7b7923cce2ef8840badd9387479 | 1f4a02c4e85df4fe59b71119f13b48f6512929a73ebcedd88a6276e192eb31ad |
| `Platform/05-resource/ru/spec/05-resource.n5.cases.md` | MODIFIED | ee6b3433d96a7e1265be0d994744bff2b640dd45 | 0cdce8ee4c482a56dd9ce8e7b5fc4f2ed7a3efd5 | 9875e320618ef10bb26e9bb045585ed2b9e168bd90d8e12a63434b9da80448bc |
| `Platform/05-resource/spec/05-resource.n5.cases.md` | MODIFIED | fce8363c4c3d2847582a40d6a91861889e7c17d8 | 1a5345cceba5e549bb0b9a8cfdd6a1066b27eba7 | 738f06f461dd2018995003c47f7d152f77f49f8ab53494a6aa4b6d3f1108d7d9 |
| `Platform/common/ru/vectors/journal/README.cases.md` | MODIFIED | 4a3543a427f7935e20f2bbbbbcfa3dcd43ae96c5 | 5a888375621f80fd00df37d3cf0e0f08eb571020 | 8e6478cacaa46c1ba540ff020e0a1cb9f19bd5de752ffb369ff774957c3e53dc |
| `Platform/common/vectors/journal/README.cases.md` | MODIFIED | 618f1c08b27f09b01866823ad849737a24769509 | b0a4c3280e13ecdfd3522b68327497f20168df59 | df06691a7ce452eda43fca26d0b11b111acf918958d3a38a693d755feb193ffb |
