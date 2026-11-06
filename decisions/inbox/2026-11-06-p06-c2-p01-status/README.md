# P06 C2 related P01: actual body ceiling in status

The Architect approved the1f00 source-form and explicitly assigned this P01 change as a separate commit in the P06 joint; coord103 confirmed its source scope. Required Status.max_body is a positive integer equal to this instance's configured `-max-body`, in entity-body bytes. max_value is unchanged. The two limits are neither aliases nor defaults guessed by the installer.

N2 status source/ru and the actual OpenAPI Status form change together. Scenario16 step1 retains its previous assertions and adds the two exact default ceilings. The acceptance source/ru also requires a fresh nondefault launch through the existing flags, and contains10 full-response schema witnesses (3 positive/7 negative). The existing wire parsing, commands, flags, daemon byte behavior and other P01 schemas remain unchanged. JSON whitespace/LF counts as entity; HTTP framing does not.

Own verification: parsed OpenAPI comparison after removing only required/properties.max_body is identical to the previous source; this includes max_value. All10 complete Status schema witnesses and both changed source/ru pairs pass. These checks do not start a store or execute the configured HTTP repeat. The input fixture describes schema cases, not acceptance.yaml or a new executable installer flag. Unknown acceptance.yaml keys are runner AssemblyError and cannot stand for an installer `refused:form`.

`source-map.json` freezes the8 P01 paths and their byte hashes/deltas. The upstream source-only C2 profile/static installation check is a separate linked P02/P06 slice. No official P01 pin, export, generated output, native/SUT or full GATE is changed here. coord103 will update the official P01 pin and inform the lines only after the whole joint's merge/GATE/export.
