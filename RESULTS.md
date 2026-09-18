# Results

Generated 2026-09-18 by `scripts/make_results.py` — every block below is captured command output, not prose.

## Unit tests

`python -m pytest -q` — exit 0, OK

```
.......................                                                  [100%]
23 passed in 1.11s
```

## Seed the synthetic week

`python -m fanoutgate seed data` — exit 0, OK

```
wrote data/Site KPI Analysis (Ops Version) - 2026.09.13.xlsx
```

## Prepare: G1 on the sources, then one graded packet per resolvable lead

`python -m fanoutgate prepare data --out out/run` — exit 0, OK

```
PASS     abara-imani
PASS     brandt-tobias
PASS     calloway-renata
PASS     dimitrov-pavel
PASS     eklund-signe
PASS     farrow-desmond
PASS     galvez-lucia
PASS     haldane-fergus
PASS     ibarra-marisol
PASS     jansson-anders
PASS     kovac-mila
PASS     lindqvist-henrik
PASS     marchetti-carla
PASS     nakamura-kenji
PASS     okafor-adaeze
PASS     pruitt-wendell
PASS     quintero-paloma
PASS     rasmussen-soren
PASS     thackeray-rupert
PASS     ueda-aiko
PASS     whitlock-odette
PASS     yilmaz-emre

week ending 2026-09-13: 22/22 messages pass, 188 of 203 sites covered, 1 resolved via directory
SKIPPED  Salgado Beatriz (9 sites): 2 directory matches (beatriz.salgado@brightwater.example, bsalgado2@brightwater.example)
SKIPPED  Varga Laszlo (6 sites): not in Lead View and no directory match
```

## Send: first attempt delivers and writes the ledger per message

`python -m fanoutgate send out/run --now 2026-09-15T08:00:00` — exit 0, OK

```
sent 22, refused 0
```

## Send: the retry is refused, every message, by G6

`python -m fanoutgate send out/run` — expected non-zero exit, OK

```
REFUSED  abara-imani                  G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  brandt-tobias                G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  calloway-renata              G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  dimitrov-pavel               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  eklund-signe                 G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  farrow-desmond               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  galvez-lucia                 G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  haldane-fergus               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  ibarra-marisol               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  jansson-anders               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  kovac-mila                   G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  lindqvist-henrik             G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  marchetti-carla              G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  nakamura-kenji               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  okafor-adaeze                G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  pruitt-wendell               G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  quintero-paloma              G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  rasmussen-soren              G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  thackeray-rupert             G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  ueda-aiko                    G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  whitlock-odette              G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
REFUSED  yilmaz-emre                  G6  already sent 2026-09-15T08:00:00 - check the outbox before retrying
sent 0, refused 22
```

## Reconcile: the documented action-plan formula vs. what the workbook stores

`python -m fanoutgate reconcile data` — exit 0, OK

```
rows reconciled                       203
documented formula reproduces row     113/203 (56%)
  training lines reproduced           43/115 (37%)
  rows differing only in line order   18
stored text read verbatim reproduces  203/203 (100%) - by construction

The 'hours to add' column and the action text disagree inside the same workbook.
One of them is wrong and this pipeline does not get to decide which. It reads the text.
```

## Build the counterexamples

`python -m fanoutgate counterexamples out/cx --data data` — exit 0, OK

```
g1-stale-week              this week's announcement has arrived; the workbook on the share is still last week's
g2-ambiguous-recipient     two people in the directory share the lead's name; message addressed to the first hit
g3-foreign-site            one row from another lead's portfolio rides along in the table
g4-recomputed-action       action lines regenerated from the documented formula instead of read from the workbook
g5-rounded-number          an hours-to-add cell 'helpfully' rounded up to a whole hour
g6-retry-duplicate         send returned a connection error after delivering; the retry would message the lead twice
```

## Gate refuses every counterexample, each for its own rule

`python -m fanoutgate check-dir out/cx --send` — expected non-zero exit, OK

```
REFUSED  g1-stale-week                G1  announced week 2026-09-20 but workbook on the share is 2026-09-13 - stale
REFUSED  g2-ambiguous-recipient       G2  Salgado Beatriz: 2 directory matches (beatriz.salgado@brightwater.example, bsalgado2@brightwater.example) - skip and report, never guess
REFUSED  g3-foreign-site              G3  foreign site 'Birch Landing' (belongs to Calloway Renata)
REFUSED  g4-recomputed-action         G4  Eastgate Annex: stored line missing from message: 'Add 1.5 Tenant training hours to September' (+3 more)
REFUSED  g5-rounded-number            G5  Westmark Landing / +QA hrs: message says '3', workbook says '2.12'
REFUSED  g6-retry-duplicate           G6  already sent 2026-09-15T08:00:07 - check the outbox before retrying

0 pass, 6 refused
```
