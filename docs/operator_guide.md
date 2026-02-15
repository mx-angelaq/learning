# Kickboxing Tournament App — Operator Guide

## 1) One-time setup
1. Open the Google Sheet bound to Apps Script.
2. Paste `src/kickboxing_tournament_app.gs` into the Script Editor.
3. Run `setupTournamentSheets` once.
4. Confirm sheets exist: `Registrations`, `Matches`, `Bouts`, `Display`, `Config`.

## 2) Registration workflow
1. Keep form responses in `Form Responses 1`.
2. Run `refreshRegistrations`.
3. Verify each fighter has:
   - Division (Kids / Youth / Adult)
   - Weight Class
   - Experience Band
   - Status = Active

## 3) Build tournament brackets
1. Run `generateMatches`.
2. This groups fighters by Division + Gender + Experience Band + Weight Class.
3. It creates full single-elimination rounds, including auto walkovers for byes.

## 4) Build ring queue and display
1. Run `buildBoutQueue`.
2. Update `Bouts` sheet status per ring: `Now`, `On Deck`, `Up Next`, `Queued`, `Done`.
3. Run `buildDisplay` to refresh the announcer view.

## 5) Record results and advance winners
Use one of:
- Script call: `recordMatchResult(matchId, winnerCorner, method, notes)`
  - Example: `recordMatchResult('Adult-Male-Adult-125-150-R1M1', 'Red', 'Decision', '')`
- For walkovers/byes and missing opponents, run `advanceBracket` to auto-propagate.

## 6) Day-of scratches / no-shows
1. Run `markScratch(fighterId, reason)`.
2. The fighter is marked scratched in `Registrations`.
3. Open matches are updated; opponent auto-advances where applicable.
4. Re-run: `buildBoutQueue` and `buildDisplay`.

## 7) Configuring weight classes
Edit `Config` rows where:
- `Type = WeightClass`
- `Key = Division`
- `Value1 = Min Weight`
- `Value2 = Max Weight`
- `Value3 = Label`
