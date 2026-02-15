/**
 * Kickboxing Tournament Organizer (Google Apps Script)
 * End-to-end refactor with robust bracket generation, walkovers, scratches, and display queue.
 */

const CFG = {
  SHEETS: {
    FORM: 'Form Responses 1',
    REG: 'Registrations',
    MATCHES: 'Matches',
    BOUTS: 'Bouts',
    DISPLAY: 'Display',
    CONFIG: 'Config'
  },
  STATUS: {
    ACTIVE: 'Active',
    SCRATCH: 'Scratch',
    NO_SHOW: 'No Show'
  },
  BOUT_STATUS_PRIORITY: { Now: 0, 'On Deck': 1, 'Up Next': 2, Queued: 3, Done: 99, '': 50 },
  AGE: { KIDS_MAX: 12, YOUTH_MIN: 13, YOUTH_MAX: 17, ADULT_MIN: 18 },
  GROUP_BY_SEX: true
};

function onOpen() {
  if (!canUseSpreadsheetUi_()) {
    return;
  }
  buildTournamentMenu_();
}

function installMenu() {
  if (!canUseSpreadsheetUi_()) {
    throw new Error('Menu requires a spreadsheet-bound script. Open the linked Google Sheet and run this there.');
  }
  buildTournamentMenu_();
}

function buildTournamentMenu_() {
  SpreadsheetApp.getUi()
    .createMenu('Tournament')
    .addItem('1) Setup / Repair Sheets', 'setupTournamentSheets')
    .addItem('2) Refresh Registrations', 'refreshRegistrations')
    .addItem('3) Generate Brackets + Matches', 'generateMatches')
    .addItem('4) Build Bout Queue', 'buildBoutQueue')
    .addItem('5) Build Display', 'buildDisplay')
    .addSeparator()
    .addItem('Advance Winners (auto propagate)', 'advanceBracket')
    .addToUi();
}

function canUseSpreadsheetUi_() {
  try {
    SpreadsheetApp.getUi();
    return true;
  } catch (error) {
    return false;
  }
}

function setupTournamentSheets() {
  const ss = SpreadsheetApp.getActive();
  ensureSheet_(ss, CFG.SHEETS.REG, [
    'Fighter ID', 'Name', 'Gender', 'Weight', 'Age', 'Gym', 'Experience Years',
    'Phone', 'Emergency Contact', 'Medical Notes', 'Division', 'Weight Class',
    'Experience Band', 'Status', 'Notes', 'Created At'
  ]);
  ensureSheet_(ss, CFG.SHEETS.MATCHES, [
    'Match ID', 'Division Key', 'Division', 'Gender', 'Weight Class', 'Experience Band',
    'Round', 'Round Match',
    'Red Fighter ID', 'Red Name', 'Red Gym',
    'Blue Fighter ID', 'Blue Name', 'Blue Gym',
    'Winner ID', 'Winner Name', 'Result Method', 'Result Notes',
    'Auto Reason', 'Next Match ID', 'Next Corner',
    'Ring', 'Sequence', 'Bout Status', 'Last Updated'
  ]);
  ensureSheet_(ss, CFG.SHEETS.BOUTS, [
    'Sequence', 'Ring', 'Bout Status', 'Match ID', 'Division', 'Round',
    'Red', 'Blue', 'Weight Class', 'Experience Band'
  ]);
  ensureSheet_(ss, CFG.SHEETS.DISPLAY, ['Ring', 'Now', 'On Deck', 'Up Next']);

  const cfg = ensureSheet_(ss, CFG.SHEETS.CONFIG, ['Type', 'Key', 'Value1', 'Value2', 'Value3']);
  if (cfg.getLastRow() === 1) {
    cfg.getRange(2, 1, 11, 5).setValues([
      ['WeightClass', 'Kids', 0, 55, 'Kids 0-55'],
      ['WeightClass', 'Kids', 55.01, 75, 'Kids 55-75'],
      ['WeightClass', 'Kids', 75.01, 999, 'Kids 75+'],
      ['WeightClass', 'Youth', 0, 100, 'Youth 0-100'],
      ['WeightClass', 'Youth', 100.01, 130, 'Youth 100-130'],
      ['WeightClass', 'Youth', 130.01, 999, 'Youth 130+'],
      ['WeightClass', 'Adult', 0, 125, 'Adult 0-125'],
      ['WeightClass', 'Adult', 125.01, 150, 'Adult 125-150'],
      ['WeightClass', 'Adult', 150.01, 175, 'Adult 150-175'],
      ['WeightClass', 'Adult', 175.01, 999, 'Adult 175+'],
      ['Meta', 'Version', '2.0', '', '']
    ]);
  }
}

function refreshRegistrations() {
  const ss = SpreadsheetApp.getActive();
  const form = ss.getSheetByName(CFG.SHEETS.FORM);
  const reg = ss.getSheetByName(CFG.SHEETS.REG);
  if (!form || !reg) throw new Error('Missing required sheet(s): Form Responses 1 and/or Registrations');

  const values = form.getDataRange().getValues();
  reg.getRange(2, 1, Math.max(0, reg.getLastRow() - 1), reg.getLastColumn()).clearContent();
  if (values.length < 2) return;

  const header = values[0].map(v => canon_(v));
  const c = (aliases) => {
    for (const alias of aliases) {
      const idx = header.indexOf(canon_(alias));
      if (idx >= 0) return idx;
    }
    return -1;
  };

  const idx = {
    name: c(['Name', 'Fighter Name', 'Competitor Name']),
    gender: c(['Sex', 'Gender']),
    weight: c(['Weight', 'Weight (lbs)', 'Weight lbs']),
    age: c(['Age']),
    gym: c(['Gym', 'Gym/Team', 'Team']),
    exp: c(['Years of experience', 'Experience', 'Experience level']),
    phone: c(['Phone', 'Competitor: Phone']),
    emergencyName: c(['Emergency contact: Name', 'Emergency Contact Name']),
    emergencyPhone: c(['Emergency contact: Phone', 'Emergency Contact Phone']),
    medical: c(['Medical', 'Medical notes'])
  };

  const required = ['name', 'weight', 'age'];
  const missing = required.filter(k => idx[k] < 0);
  if (missing.length) throw new Error(`Missing required columns in form sheet: ${missing.join(', ')}`);

  const out = [];
  let seq = 1;
  for (const row of values.slice(1)) {
    const name = safeStr_(row[idx.name]);
    if (!name) continue;

    const age = toNum_(row[idx.age]);
    const division = divisionFromAge_(age);
    const weight = toNum_(row[idx.weight]);
    const expYears = toNum_(row[idx.exp]);

    out.push([
      `F${String(seq++).padStart(4, '0')}`,
      name,
      canonGender_(row[idx.gender]),
      weight,
      age,
      safeStr_(row[idx.gym]),
      Number.isFinite(expYears) ? expYears : '',
      safeStr_(row[idx.phone]),
      formatEmergency_(row[idx.emergencyName], row[idx.emergencyPhone]),
      safeStr_(row[idx.medical]),
      division,
      lookupWeightClass_(division, weight),
      experienceBand_(expYears),
      CFG.STATUS.ACTIVE,
      '',
      new Date()
    ]);
  }

  if (out.length) reg.getRange(2, 1, out.length, out[0].length).setValues(out);
}

function generateMatches() {
  const ss = SpreadsheetApp.getActive();
  const reg = mustSheet_(ss, CFG.SHEETS.REG);
  const matches = mustSheet_(ss, CFG.SHEETS.MATCHES);

  const data = reg.getDataRange().getValues();
  if (data.length < 2) {
    clearSheetBody_(matches);
    return;
  }

  const h = toIndex_(data[0]);
  const fighters = data.slice(1).map(r => ({
    id: safeStr_(r[h['Fighter ID']]),
    name: safeStr_(r[h['Name']]),
    gender: safeStr_(r[h['Gender']]),
    weight: toNum_(r[h['Weight']]),
    age: toNum_(r[h['Age']]),
    gym: safeStr_(r[h['Gym']]),
    division: safeStr_(r[h['Division']]),
    weightClass: safeStr_(r[h['Weight Class']]),
    expBand: safeStr_(r[h['Experience Band']]),
    status: safeStr_(r[h['Status']]) || CFG.STATUS.ACTIVE
  })).filter(f => f.id && f.name && f.status === CFG.STATUS.ACTIVE);

  const groups = groupFighters_(fighters);
  const rows = [];
  Object.keys(groups).sort().forEach(key => {
    const group = groups[key];
    const structure = buildDivisionBracket_(group, key);
    rows.push(...structure);
  });

  clearSheetBody_(matches);
  if (rows.length) matches.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  advanceBracket();
}

function advanceBracket() {
  const ss = SpreadsheetApp.getActive();
  const sh = mustSheet_(ss, CFG.SHEETS.MATCHES);
  const data = sh.getDataRange().getValues();
  if (data.length < 2) return;

  const h = toIndex_(data[0]);
  const byId = {};
  const rows = data.slice(1).map((r, i) => {
    const row = {
      sheetRow: i + 2,
      matchId: safeStr_(r[h['Match ID']]),
      divisionKey: safeStr_(r[h['Division Key']]),
      redId: safeStr_(r[h['Red Fighter ID']]),
      redName: safeStr_(r[h['Red Name']]),
      blueId: safeStr_(r[h['Blue Fighter ID']]),
      blueName: safeStr_(r[h['Blue Name']]),
      winnerId: safeStr_(r[h['Winner ID']]),
      winnerName: safeStr_(r[h['Winner Name']]),
      method: safeStr_(r[h['Result Method']]),
      notes: safeStr_(r[h['Result Notes']]),
      autoReason: safeStr_(r[h['Auto Reason']]),
      nextId: safeStr_(r[h['Next Match ID']]),
      nextCorner: safeStr_(r[h['Next Corner']])
    };
    byId[row.matchId] = row;
    return row;
  });

  let changed = true;
  while (changed) {
    changed = false;
    for (const m of rows) {
      if (m.winnerId) {
        changed = pushWinnerToNext_(m, byId, h, sh) || changed;
        continue;
      }
      const redPresent = !!m.redId;
      const bluePresent = !!m.blueId;
      if (redPresent && !bluePresent) {
        m.winnerId = m.redId;
        m.winnerName = m.redName;
        m.method = m.method || 'Walkover';
        m.autoReason = m.autoReason || 'Blue missing';
        writeWinner_(m, h, sh);
        changed = true;
        changed = pushWinnerToNext_(m, byId, h, sh) || changed;
      } else if (!redPresent && bluePresent) {
        m.winnerId = m.blueId;
        m.winnerName = m.blueName;
        m.method = m.method || 'Walkover';
        m.autoReason = m.autoReason || 'Red missing';
        writeWinner_(m, h, sh);
        changed = true;
        changed = pushWinnerToNext_(m, byId, h, sh) || changed;
      }
    }
  }
}

function buildBoutQueue() {
  const ss = SpreadsheetApp.getActive();
  const matches = mustSheet_(ss, CFG.SHEETS.MATCHES);
  const bouts = mustSheet_(ss, CFG.SHEETS.BOUTS);

  const data = matches.getDataRange().getValues();
  if (data.length < 2) {
    clearSheetBody_(bouts);
    return;
  }
  const h = toIndex_(data[0]);

  const queue = data.slice(1)
    .filter(r => !safeStr_(r[h['Winner ID']]))
    .filter(r => safeStr_(r[h['Red Fighter ID']]) && safeStr_(r[h['Blue Fighter ID']]))
    .sort((a, b) => Number(a[h['Round']]) - Number(b[h['Round']]) || safeStr_(a[h['Match ID']]).localeCompare(safeStr_(b[h['Match ID']])))
    .map((r, i) => [
      Number(r[h['Sequence']]) || i + 1,
      safeStr_(r[h['Ring']]) || (i % 2 ? 'Ring 2' : 'Ring 1'),
      safeStr_(r[h['Bout Status']]) || 'Queued',
      safeStr_(r[h['Match ID']]),
      safeStr_(r[h['Division']]),
      Number(r[h['Round']]) || 1,
      safeStr_(r[h['Red Name']]),
      safeStr_(r[h['Blue Name']]),
      safeStr_(r[h['Weight Class']]),
      safeStr_(r[h['Experience Band']])
    ]);

  clearSheetBody_(bouts);
  if (queue.length) bouts.getRange(2, 1, queue.length, queue[0].length).setValues(queue);
}

function buildDisplay() {
  const ss = SpreadsheetApp.getActive();
  const bouts = mustSheet_(ss, CFG.SHEETS.BOUTS);
  const display = mustSheet_(ss, CFG.SHEETS.DISPLAY);
  const data = bouts.getDataRange().getValues();

  display.clearContents();
  display.getRange(1, 1, 1, 4).setValues([['Ring', 'Now', 'On Deck', 'Up Next']]);
  if (data.length < 2) return;

  const h = toIndex_(data[0]);
  const rows = data.slice(1)
    .filter(r => safeStr_(r[h['Match ID']]))
    .filter(r => safeStr_(r[h['Bout Status']]) !== 'Done')
    .map(r => ({
      ring: safeStr_(r[h['Ring']]) || 'Ring 1',
      status: safeStr_(r[h['Bout Status']]) || 'Queued',
      text: `${safeStr_(r[h['Red']])} vs ${safeStr_(r[h['Blue']])}\n${safeStr_(r[h['Division']])} / ${safeStr_(r[h['Weight Class']])}`
    }));

  const rings = {};
  rows.forEach(r => {
    if (!rings[r.ring]) rings[r.ring] = [];
    rings[r.ring].push(r);
  });

  const out = [];
  Object.keys(rings).sort().forEach(ring => {
    const list = rings[ring].sort((a, b) => (CFG.BOUT_STATUS_PRIORITY[a.status] ?? 50) - (CFG.BOUT_STATUS_PRIORITY[b.status] ?? 50));
    const now = list.find(x => x.status === 'Now') || list[0];
    const deck = list.find(x => x.status === 'On Deck') || list.find(x => x !== now) || null;
    const next = list.find(x => x.status === 'Up Next') || list.find(x => x !== now && x !== deck) || null;
    out.push([ring, now ? now.text : '', deck ? deck.text : '', next ? next.text : '']);
  });

  if (out.length) display.getRange(2, 1, out.length, 4).setValues(out);
}

function recordMatchResult(matchId, winnerCorner, method, notes) {
  const ss = SpreadsheetApp.getActive();
  const sh = mustSheet_(ss, CFG.SHEETS.MATCHES);
  const data = sh.getDataRange().getValues();
  if (data.length < 2) throw new Error('No match data found.');

  const h = toIndex_(data[0]);
  const idx = data.slice(1).findIndex(r => safeStr_(r[h['Match ID']]) === matchId);
  if (idx < 0) throw new Error(`Match not found: ${matchId}`);

  const rowNum = idx + 2;
  const row = data[rowNum - 1];
  const isRed = canon_(winnerCorner) === 'red';
  const winnerId = isRed ? safeStr_(row[h['Red Fighter ID']]) : safeStr_(row[h['Blue Fighter ID']]);
  const winnerName = isRed ? safeStr_(row[h['Red Name']]) : safeStr_(row[h['Blue Name']]);
  if (!winnerId) throw new Error(`Winner corner has no fighter in match ${matchId}`);

  sh.getRange(rowNum, h['Winner ID'] + 1, 1, 5).setValues([[winnerId, winnerName, safeStr_(method), safeStr_(notes), '']]);
  sh.getRange(rowNum, h['Last Updated'] + 1).setValue(new Date());
  advanceBracket();
}

function markScratch(fighterId, reason) {
  const ss = SpreadsheetApp.getActive();
  const reg = mustSheet_(ss, CFG.SHEETS.REG);
  const matches = mustSheet_(ss, CFG.SHEETS.MATCHES);

  const regData = reg.getDataRange().getValues();
  const rh = toIndex_(regData[0]);
  for (let i = 1; i < regData.length; i++) {
    if (safeStr_(regData[i][rh['Fighter ID']]) === fighterId) {
      reg.getRange(i + 1, rh['Status'] + 1).setValue(CFG.STATUS.SCRATCH);
      reg.getRange(i + 1, rh['Notes'] + 1).setValue(`Scratch: ${safeStr_(reason)}`);
      break;
    }
  }

  const md = matches.getDataRange().getValues();
  const mh = toIndex_(md[0]);
  for (let i = 1; i < md.length; i++) {
    let changed = false;
    if (safeStr_(md[i][mh['Red Fighter ID']]) === fighterId && !safeStr_(md[i][mh['Winner ID']])) {
      md[i][mh['Red Fighter ID']] = '';
      md[i][mh['Red Name']] = '';
      md[i][mh['Red Gym']] = '';
      md[i][mh['Auto Reason']] = `Scratch ${fighterId}`;
      changed = true;
    }
    if (safeStr_(md[i][mh['Blue Fighter ID']]) === fighterId && !safeStr_(md[i][mh['Winner ID']])) {
      md[i][mh['Blue Fighter ID']] = '';
      md[i][mh['Blue Name']] = '';
      md[i][mh['Blue Gym']] = '';
      md[i][mh['Auto Reason']] = `Scratch ${fighterId}`;
      changed = true;
    }
    if (changed) {
      matches.getRange(i + 1, 1, 1, md[i].length).setValues([md[i]]);
    }
  }

  advanceBracket();
  buildBoutQueue();
  buildDisplay();
}

/** ------------------------------ Internal helpers ------------------------------ */

function buildDivisionBracket_(fighters, divisionKey) {
  if (!fighters.length) return [];
  const [division, gender, expBand, weightClass] = divisionKey.split('||');

  const seeded = seedAvoidSameGym_(fighters.slice());
  const size = nextPowerOf2_(seeded.length);
  const slots = new Array(size).fill(null);
  const seedOrder = seedSlotOrder_(size);
  seeded.forEach((fighter, i) => {
    slots[seedOrder[i] - 1] = fighter;
  });

  const rounds = Math.log(size) / Math.log(2);
  const rows = [];
  let matchSeq = 1;
  const idByRoundMatch = {};

  for (let round = 1; round <= rounds; round++) {
    const matchesInRound = size / Math.pow(2, round);
    for (let rm = 1; rm <= matchesInRound; rm++) {
      const matchId = `${slug_(division)}-${slug_(gender || 'X')}-${slug_(weightClass)}-R${round}M${rm}`;
      idByRoundMatch[`${round}-${rm}`] = matchId;

      let red = { id: '', name: '', gym: '' };
      let blue = { id: '', name: '', gym: '' };
      if (round === 1) {
        const a = slots[(rm - 1) * 2];
        const b = slots[(rm - 1) * 2 + 1];
        red = a ? { id: a.id, name: a.name, gym: a.gym } : red;
        blue = b ? { id: b.id, name: b.name, gym: b.gym } : blue;
      }

      const nextRound = round + 1;
      const nextMatch = nextRound <= rounds ? Math.ceil(rm / 2) : null;
      const nextCorner = rm % 2 ? 'Red' : 'Blue';

      rows.push([
        matchId,
        divisionKey,
        division,
        gender,
        weightClass,
        expBand,
        round,
        rm,
        red.id, red.name, red.gym,
        blue.id, blue.name, blue.gym,
        '', '', '', '',
        '',
        nextMatch ? `PENDING-R${nextRound}M${nextMatch}` : '',
        nextMatch ? nextCorner : '',
        '',
        matchSeq++,
        'Queued',
        new Date()
      ]);
    }
  }

  // Replace pending next IDs with real IDs
  rows.forEach(r => {
    if (r[19] && r[19].indexOf('PENDING-') === 0) {
      const token = r[19].replace('PENDING-', '').replace('R', '').replace('M', '-');
      r[19] = idByRoundMatch[token] || '';
    }
  });

  return rows;
}

function groupFighters_(fighters) {
  const groups = {};
  fighters.forEach(f => {
    const gender = CFG.GROUP_BY_SEX ? (f.gender || 'Open') : 'Open';
    const key = [f.division || 'Adult', gender, f.expBand || 'Mixed', f.weightClass || 'Open'].join('||');
    if (!groups[key]) groups[key] = [];
    groups[key].push(f);
  });
  return groups;
}

function seedAvoidSameGym_(fighters) {
  const shuffled = fighters.slice();
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  shuffled.sort((a, b) => safeStr_(a.gym).localeCompare(safeStr_(b.gym)) || toNum_(a.weight) - toNum_(b.weight));
  return shuffled;
}

function pushWinnerToNext_(match, byId, h, sh) {
  if (!match.nextId || !match.winnerId) return false;
  const next = byId[match.nextId];
  if (!next) return false;

  const wantsRed = canon_(match.nextCorner) === 'red';
  if (wantsRed && next.redId === match.winnerId) return false;
  if (!wantsRed && next.blueId === match.winnerId) return false;

  if (wantsRed) {
    next.redId = match.winnerId;
    next.redName = match.winnerName;
  } else {
    next.blueId = match.winnerId;
    next.blueName = match.winnerName;
  }

  const targetRow = next.sheetRow;
  if (wantsRed) {
    sh.getRange(targetRow, h['Red Fighter ID'] + 1, 1, 2).setValues([[next.redId, next.redName]]);
  } else {
    sh.getRange(targetRow, h['Blue Fighter ID'] + 1, 1, 2).setValues([[next.blueId, next.blueName]]);
  }
  sh.getRange(targetRow, h['Last Updated'] + 1).setValue(new Date());
  return true;
}

function writeWinner_(m, h, sh) {
  sh.getRange(m.sheetRow, h['Winner ID'] + 1, 1, 5).setValues([[m.winnerId, m.winnerName, m.method, m.notes, m.autoReason]]);
  sh.getRange(m.sheetRow, h['Last Updated'] + 1).setValue(new Date());
}

function lookupWeightClass_(division, weight) {
  const ss = SpreadsheetApp.getActive();
  const cfg = ss.getSheetByName(CFG.SHEETS.CONFIG);
  if (!cfg) return `${division} Open`;

  const rows = cfg.getDataRange().getValues().slice(1)
    .filter(r => safeStr_(r[0]) === 'WeightClass' && safeStr_(r[1]) === division)
    .map(r => ({ min: toNum_(r[2]), max: toNum_(r[3]), label: safeStr_(r[4]) }));

  for (const row of rows) {
    if (Number.isFinite(weight) && weight >= row.min && weight <= row.max) return row.label;
  }
  return `${division} Open`;
}

function experienceBand_(years) {
  if (!Number.isFinite(years)) return 'Unknown';
  if (years < 1) return '0-1 years';
  if (years < 3) return '1-3 years';
  if (years < 6) return '3-6 years';
  return '6+ years';
}

function divisionFromAge_(age) {
  if (!Number.isFinite(age)) return 'Adult';
  if (age <= CFG.AGE.KIDS_MAX) return 'Kids';
  if (age >= CFG.AGE.YOUTH_MIN && age <= CFG.AGE.YOUTH_MAX) return 'Youth';
  return 'Adult';
}

function seedSlotOrder_(size) {
  if (size === 1) return [1];
  let seeds = [1, 2];
  while (seeds.length < size) {
    const next = [];
    const m = seeds.length * 2 + 1;
    seeds.forEach(s => {
      next.push(s);
      next.push(m - s);
    });
    seeds = next;
  }
  return seeds;
}

function nextPowerOf2_(n) {
  let p = 1;
  while (p < n) p *= 2;
  return p;
}

function ensureSheet_(ss, name, header) {
  const sh = ss.getSheetByName(name) || ss.insertSheet(name);
  const existing = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), header.length)).getValues()[0];
  const needsHeader = !existing[0] || header.some((h, i) => safeStr_(existing[i]) !== h);
  if (needsHeader) sh.getRange(1, 1, 1, header.length).setValues([header]);
  return sh;
}

function clearSheetBody_(sh) {
  if (sh.getLastRow() > 1) sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).clearContent();
}

function mustSheet_(ss, name) {
  const sh = ss.getSheetByName(name);
  if (!sh) throw new Error(`Missing required sheet: ${name}`);
  return sh;
}

function toIndex_(headerRow) {
  const out = {};
  headerRow.forEach((c, i) => { out[safeStr_(c)] = i; });
  return out;
}

function toNum_(value) {
  const n = Number(String(value).replace(/[^0-9.-]/g, ''));
  return Number.isFinite(n) ? n : NaN;
}

function safeStr_(value) {
  return value === null || value === undefined ? '' : String(value).trim();
}

function canon_(value) {
  return safeStr_(value).toLowerCase().replace(/\s+/g, ' ');
}

function canonGender_(value) {
  const c = canon_(value);
  if (c === 'm' || c === 'male') return 'Male';
  if (c === 'f' || c === 'female') return 'Female';
  return c ? c[0].toUpperCase() + c.slice(1) : '';
}

function formatEmergency_(name, phone) {
  const n = safeStr_(name);
  const p = safeStr_(phone);
  if (n && p) return `Name: ${n} / Phone: ${p}`;
  return n || p;
}

function slug_(s) {
  return safeStr_(s).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
