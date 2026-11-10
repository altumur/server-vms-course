# Change 0130-p01-d7-payload

change: 0130-p01-d7-payload rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `b0a0cfaa5e3798f6fe0e56dd70407d23d5f355be`. Task P01.136, ADR-0130 plan row 5, the condition of P01.132; the Architect's answer on P01.136 (two commits). (1) The model-visible form `Platform/common/acceptance/forms/d7-payload.schema.json`: the payloads of the D7 requests and records by capability (clock, storage, progress, fault) and operation; a paragraph of README «D7 test-side evidence bindings» EN/RU names it, and the closing sentence no longer says that no payload form exists. No numeric value; both filters name the form. No requirement unit changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/README.md` | MODIFIED | f0ad500fb8af4ee0b488223b61ffeb2baf61f02b | 37835175f10623be0cb4ae4053cc21fa451f0394 | 24f4e38e9f47fb552e3abe21df5972294f4208de77989755d64b6acdad809607 |
| `Platform/common/acceptance/forms/d7-payload.schema.json` | ADDED | - | 5bdd4bc8350b24b40fcbf024930bc100ce8798e4 | 6ac96fdd626ad3fc110b6b5e16e73a5a6ca17a20f8a96655a38422a52756ed7c |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | ec0fc004e242d9a441bb4042b5a226f80ae4df17 | 20b5962a32a9678675b0359863ee08a48f7e8ac1 | b7fba146b0e593dd19fd7030f067b91670fc2a5984eb13f77d6e4f541f678768 |
| `Platform/common/export-model-filter.json` | MODIFIED | 5b1bb97c01cabb4a7865dfd4ff18e62e3b83fd1a | 230d2756547b3f13128e723648ca6694fac39b7d | 4207fa64eae34793b49ddc5d6ac6771ebeadeedb575272cdeb80fb776cba8ada |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | e88bd5fc0a4cf9f3212e51df14d1f6059e09944e | 8daf30d6822ca571fe981b4138b4abc914e99e07 | 0a5805bf50e80d1bb5c7be33a5648948a689adfaf87682543cc668830a36df05 |
