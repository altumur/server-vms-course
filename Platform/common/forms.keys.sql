-- The keys between the forms of Platform (OBSH.39, ADR-0125 addendum (12) item 2): DDL only, no rows. First group: forms/stages.tsv and
-- forms/code-rules.tsv of a lesson, the closed dictionary Platform/common/acceptance/forms/code-rules.tsv and the checklist items of the norms.
-- The check loads the projections below into an in-memory SQLite with PRAGMA foreign_keys=ON before the transaction; deferred keys hold at COMMIT.
-- lesson: the lesson key P/NN (P/01 for Platform/01-store). Values are the raw TEXT of the cells, without trim, except the strip of the elements of norms.
-- stage: a data row of forms/stages.tsv; n is the cell n, read as INTEGER only after its sidecar schema has checked the raw lexical form;
--   code_gate is 1 when code:* is an element of the cell gate split by ;, else 0. forms/stages.kit.tsv is not loaded.
-- code_kind: a data row of the dictionary: kind, and name_type = the cell name.
-- code_rule: a data row of forms/code-rules.tsv of the lesson: the cells id, kind, name, stage.
-- norm_item: a checklist item - [ ] **P/NN.K-MM** of the section «Readiness checklist» of spec/*.norms.md of the lesson.
-- stage_norm: an element of the cell norms of forms/stages.tsv that, after strip, is exactly P/NN.K-MM, with the cell stage of its row.
-- required_norm_item: the rows of norm_item of a lesson that must place every item (now P/01); an item at no stage fails at COMMIT.
-- Not expressed here, kept by the existing checks: code:* in the own or a later stage of a code row, n in physical order, depends on former
-- stages, one name type per name, args as JSON with the fields of the kind, when as CEL, the owner and the non-empty roster of the lesson.

CREATE TABLE stage (
  lesson    TEXT    NOT NULL,
  stage     TEXT    NOT NULL,
  n         INTEGER NOT NULL CHECK (n >= 1),
  code_gate INTEGER NOT NULL CHECK (code_gate IN (0, 1)),
  PRIMARY KEY (lesson, stage),
  UNIQUE (lesson, n)
);

CREATE TABLE code_kind (
  kind      TEXT NOT NULL PRIMARY KEY,
  name_type TEXT NOT NULL CHECK (name_type IN ('package', 'function', 'type', 'package or function'))
);

CREATE TABLE code_rule (
  lesson TEXT NOT NULL,
  id     TEXT NOT NULL,
  kind   TEXT NOT NULL,
  name   TEXT NOT NULL,
  stage  TEXT NOT NULL,
  PRIMARY KEY (lesson, id),
  FOREIGN KEY (kind) REFERENCES code_kind (kind),
  FOREIGN KEY (lesson, stage) REFERENCES stage (lesson, stage)
);

CREATE TABLE norm_item (
  lesson TEXT NOT NULL,
  item   TEXT NOT NULL,
  PRIMARY KEY (lesson, item)
);

CREATE TABLE stage_norm (
  lesson TEXT NOT NULL,
  item   TEXT NOT NULL,
  stage  TEXT NOT NULL,
  PRIMARY KEY (lesson, item),
  FOREIGN KEY (lesson, stage) REFERENCES stage (lesson, stage),
  FOREIGN KEY (lesson, item) REFERENCES norm_item (lesson, item)
);

CREATE TABLE required_norm_item (
  lesson TEXT NOT NULL,
  item   TEXT NOT NULL,
  PRIMARY KEY (lesson, item),
  FOREIGN KEY (lesson, item) REFERENCES norm_item (lesson, item),
  FOREIGN KEY (lesson, item) REFERENCES stage_norm (lesson, item) DEFERRABLE INITIALLY DEFERRED
);
