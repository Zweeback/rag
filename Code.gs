/**
 * Serves the Alice + Archivator web application.
 */
function doGet() {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Alice – Archivator Assistant')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * Runs the archivator "start of day" routine.
 * Collects today's calendar events, unread mail, new contacts and recent Drive files.
 * @return {Object} structured summary that can be formatted for voice output.
 */
function startDay() {
  const today = new Date();
  const midnight = new Date(today);
  midnight.setHours(0, 0, 0, 0);
  const tomorrow = new Date(midnight);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const events = CalendarApp.getDefaultCalendar().getEvents(midnight, tomorrow).map((event) => ({
    title: event.getTitle(),
    start: event.getStartTime(),
    end: event.getEndTime(),
    location: event.getLocation() || ''
  }));

  const threads = GmailApp.search('label:inbox is:unread newer_than:7d', 0, 10);
  const unreadMail = threads.map((thread) => ({
    subject: thread.getFirstMessageSubject(),
    from: thread.getMessages()[0].getFrom(),
    snippet: thread.getMessages()[0].getPlainBody().slice(0, 160)
  }));

  const contacts = ContactsApp.getContactsByDate(ContactsApp.Field.LAST_UPDATED, midnight, tomorrow).map((contact) => ({
    name: contact.getFullName(),
    email: (contact.getEmails()[0] && contact.getEmails()[0].getAddress()) || '',
    lastUpdated: contact.getLastUpdated()
  }));

  const driveFiles = listRecentDriveFiles();

  const summary = {
    generatedAt: today,
    events: events,
    unreadMail: unreadMail,
    contacts: contacts,
    driveFiles: driveFiles
  };

  Logger.log('Start-day summary: %s', JSON.stringify(summary));
  return summary;
}

/**
 * Moves stale Drive files into the trash so the archive stays lean.
 * @return {Object} result information for voice feedback.
 */
function cleanup() {
  const folderId = getSecret('ARCHIVATOR_INBOX_FOLDER_ID');
  if (!folderId) {
    Logger.log('No ARCHIVATOR_INBOX_FOLDER_ID configured; skipping cleanup.');
    return { trashedCount: 0, affected: [], message: 'Kein Zielordner konfiguriert.' };
  }

  const folder = DriveApp.getFolderById(folderId);
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 30);

  const iterator = folder.getFiles();
  let trashed = 0;
  const affected = [];
  while (iterator.hasNext()) {
    const file = iterator.next();
    if (file.getLastUpdated() < cutoff) {
      file.setTrashed(true);
      trashed += 1;
      affected.push({ id: file.getId(), name: file.getName() });
    }
  }

  const result = {
    trashedCount: trashed,
    affected: affected
  };

  Logger.log('Cleanup trashed %s files from folder %s', trashed, folder.getName());
  return result;
}

/**
 * Updates the Drive index sheet with the latest file metadata.
 * Configure the sheet ID in Script Properties under the key INDEX_SHEET_ID.
 * @return {Object} details about the indexing run.
 */
function updateIndexes() {
  const spreadsheetId = getSecret('INDEX_SHEET_ID');
  if (!spreadsheetId) {
    Logger.log('No INDEX_SHEET_ID configured.');
    return { updated: false, message: 'Kein Index-Spreadsheet hinterlegt.' };
  }

  const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  const sheetName = 'Drive Index';
  const sheet = spreadsheet.getSheetByName(sheetName) || spreadsheet.insertSheet(sheetName);
  sheet.clear();
  sheet.appendRow(['Name', 'ID', 'Besitzer', 'Zuletzt geändert']);

  let pageToken;
  let count = 0;
  do {
    const response = Drive.Files.list({
      q: "trashed = false",
      pageSize: 100,
      fields: 'nextPageToken, files(id, name, owners(displayName), modifiedTime)',
      pageToken: pageToken
    });

    const files = response.files || [];
    files.forEach((file) => {
      const owner = file.owners && file.owners.length ? file.owners[0].displayName : '';
      sheet.appendRow([file.name, file.id, owner, file.modifiedTime]);
      count += 1;
    });

    pageToken = response.nextPageToken;
  } while (pageToken);

  Logger.log('Drive index updated with %s entries.', count);
  return { updated: true, entries: count };
}

/**
 * Scans recent export mails and attachments for further processing.
 * @return {Object} summary of discovered export files.
 */
function scanExports() {
  const threads = GmailApp.search('subject:(Export OR Bericht) newer_than:14d', 0, 20);
  const exports = [];

  threads.forEach((thread) => {
    thread.getMessages().forEach((message) => {
      message.getAttachments().forEach((attachment) => {
        exports.push({
          threadId: thread.getId(),
          name: attachment.getName(),
          size: attachment.getSize()
        });
      });
    });
  });

  const result = {
    threads: threads.length,
    attachments: exports
  };

  Logger.log('Scan exports found %s attachments in %s threads.', exports.length, threads.length);
  return result;
}

/**
 * Processes the spoken text, routes to archivator actions or asks the AI assistant.
 * @param {string} text
 * @return {string} message to speak back to the user.
 */
function processVoiceCommand(text) {
  if (!text) {
    return 'Ich habe nichts verstanden. Bitte versuche es erneut.';
  }

  try {
    const normalized = text.toLowerCase();
    if (normalized.includes('start')) {
      const summary = startDay();
      return formatStartDaySummary(summary);
    }
    if (normalized.includes('cleanup') || normalized.includes('aufräumen')) {
      const result = cleanup();
      if (result.message && !result.trashedCount) {
        return 'Bereinigung übersprungen: ' + result.message;
      }
      return 'Bereinigung abgeschlossen. ' + result.trashedCount + ' Dateien wurden in den Papierkorb verschoben.';
    }
    if (normalized.includes('update') || normalized.includes('index')) {
      const result = updateIndexes();
      if (result.updated) {
        return 'Die Indexe wurden aktualisiert. ' + result.entries + ' Einträge sind jetzt aufgelistet.';
      }
      return 'Index-Aktualisierung übersprungen: ' + result.message;
    }
    if (normalized.includes('scan') || normalized.includes('export')) {
      const result = scanExports();
      return 'Ich habe ' + result.attachments.length + ' Export-Dateien in ' + result.threads + ' E-Mails gefunden.';
    }

    const answer = askOpenAI(text);
    return answer;
  } catch (error) {
    Logger.log('Error processing voice command: %s', error.stack || error);
    return 'Es ist ein Fehler aufgetreten: ' + error.message;
  }
}

/**
 * Fetches a secret from Script Properties.
 * @param {string} name key of the secret.
 * @return {string|null} stored secret value.
 */
function getSecret(name) {
  return PropertiesService.getScriptProperties().getProperty(name);
}

/**
 * Schedules the startDay routine every morning at 06:00 in the script timezone.
 * Run this once after deployment.
 */
function createDailyTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers
    .filter((trigger) => trigger.getHandlerFunction() === 'startDay')
    .forEach((trigger) => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger('startDay')
    .timeBased()
    .atHour(6)
    .everyDays(1)
    .create();
}

/**
 * Calls the OpenAI API with the user prompt.
 * @param {string} prompt
 * @return {string} assistant reply.
 */
function askOpenAI(prompt) {
  const apiKey = getSecret('OPENAI_API_KEY');
  if (!apiKey) {
    throw new Error('Bitte hinterlege den OpenAI API-Schlüssel in den Projekteigenschaften (OPENAI_API_KEY).');
  }

  const endpoint = 'https://api.openai.com/v1/chat/completions';
  const payload = {
    model: 'gpt-4o-mini',
    messages: [
      {
        role: 'system',
        content: 'Du bist Alice, eine freundliche digitale Assistentin. Antworte immer auf Deutsch und fasse dich klar und prägnant.'
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    temperature: 0.6
  };

  const options = {
    method: 'post',
    headers: {
      Authorization: 'Bearer ' + apiKey,
      'Content-Type': 'application/json'
    },
    muteHttpExceptions: true,
    payload: JSON.stringify(payload)
  };

  const response = UrlFetchApp.fetch(endpoint, options);
  const statusCode = response.getResponseCode();
  const body = response.getContentText();
  if (statusCode !== 200) {
    Logger.log('OpenAI API error (%s): %s', statusCode, body);
    throw new Error('Die Anfrage an das Sprachmodell ist fehlgeschlagen.');
  }

  const data = JSON.parse(body);
  const choice = data.choices && data.choices.length ? data.choices[0] : null;
  const message = choice && choice.message && choice.message.content;
  return (message && message.trim()) || 'Ich habe keine Antwort vom Sprachmodell erhalten.';
}

/**
 * Creates a compact spoken summary for the startDay() result.
 * @param {Object} summary
 * @return {string}
 */
function formatStartDaySummary(summary) {
  if (!summary) {
    return 'Es gibt heute keine neuen Informationen.';
  }

  const parts = [];
  const formatter = (date) => Utilities.formatDate(new Date(date), Session.getScriptTimeZone(), 'HH:mm');

  if (summary.events && summary.events.length) {
    const eventDescriptions = summary.events.map((event) => {
      const start = formatter(event.start);
      return start + ' – ' + event.title + (event.location ? ' in ' + event.location : '');
    });
    parts.push('Termine heute: ' + eventDescriptions.join('; '));
  }

  if (summary.unreadMail && summary.unreadMail.length) {
    parts.push('Du hast ' + summary.unreadMail.length + ' ungelesene Mails. Wichtigste Betreffzeile: ' + summary.unreadMail[0].subject + '.');
  }

  if (summary.contacts && summary.contacts.length) {
    parts.push(summary.contacts.length + ' Kontakte wurden aktualisiert.');
  }

  if (summary.driveFiles && summary.driveFiles.length) {
    parts.push('Neu in Drive: ' + summary.driveFiles.slice(0, 3).map((file) => file.name).join(', ') + '.');
  }

  if (!parts.length) {
    parts.push('Heute steht nichts Neues an. Genieße deinen Tag!');
  }

  return parts.join(' ');
}

/**
 * Lists recent Drive files modified in the last 24 hours.
 * @return {Array<Object>} file metadata objects.
 */
function listRecentDriveFiles() {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 1);
  const query = "modifiedDate > '" + cutoff.toISOString() + "' and trashed = false";
  const iterator = DriveApp.searchFiles(query);
  const files = [];

  while (iterator.hasNext()) {
    const file = iterator.next();
    files.push({
      id: file.getId(),
      name: file.getName(),
      lastUpdated: file.getLastUpdated()
    });
  }

  return files;
}

/**
 * Processes queued prompts in a Google Sheet and writes ChatGPT answers back.
 * Configure PROMPT_SHEET_ID in Script Properties and create a sheet named "Prompts"
 * with the columns: Timestamp | Prompt | Status | Response.
 */
function processSheetPrompts() {
  const sheetId = getSecret('PROMPT_SHEET_ID');
  if (!sheetId) {
    throw new Error('Bitte hinterlege die Spreadsheet-ID in den Projekteigenschaften (PROMPT_SHEET_ID).');
  }

  const sheet = SpreadsheetApp.openById(sheetId).getSheetByName('Prompts');
  if (!sheet) {
    throw new Error('Im Spreadsheet fehlt das Arbeitsblatt "Prompts".');
  }

  const rows = sheet.getDataRange().getValues();
  const updates = [];

  for (let row = 1; row < rows.length; row++) {
    const status = rows[row][2];
    const prompt = rows[row][1];
    if (!prompt || (status && status.toString().toLowerCase() === 'fertig')) {
      continue;
    }

    const response = askOpenAI(prompt);
    updates.push({ row: row + 1, response: response });
  }

  updates.forEach((update) => {
    const rowIndex = update.row;
    sheet.getRange(rowIndex, 3).setValue('Fertig');
    sheet.getRange(rowIndex, 4).setValue(update.response);
    sheet.getRange(rowIndex, 1).setValue(new Date());
  });

  return { processed: updates.length };
}

/**
 * Creates a short AI summary of the most recent files inside a Drive folder.
 * Configure WATCH_FOLDER_ID in Script Properties.
 * @return {Object} summary details.
 */
function summarizeDriveFolder() {
  const folderId = getSecret('WATCH_FOLDER_ID');
  if (!folderId) {
    throw new Error('Bitte hinterlege die Drive-Ordner-ID in den Projekteigenschaften (WATCH_FOLDER_ID).');
  }

  const folder = DriveApp.getFolderById(folderId);
  const iterator = folder.getFiles();
  const files = [];
  while (iterator.hasNext() && files.length < 10) {
    const file = iterator.next();
    files.push({
      name: file.getName(),
      updated: file.getLastUpdated(),
      url: file.getUrl()
    });
  }

  if (!files.length) {
    return { summary: 'Im beobachteten Ordner gibt es keine Dateien.' };
  }

  const prompt = 'Fasse diese Dateien für meinen Tagesüberblick knapp zusammen:\n' +
    files.map((file) => `${file.name} – aktualisiert am ${file.updated.toISOString()}`).join('\n');
  const summary = askOpenAI(prompt);

  return {
    folder: folder.getName(),
    files: files,
    summary: summary
  };
}

/**
 * Fetches the latest open GitHub issues and produces a German summary.
 * Configure GITHUB_TOKEN (classic PAT or fine-grained) and GITHUB_REPO (owner/repo).
 * @return {Object}
 */
function fetchGitHubDigest() {
  const token = getSecret('GITHUB_TOKEN');
  const repo = getSecret('GITHUB_REPO');
  if (!token || !repo) {
    throw new Error('Bitte hinterlege GITHUB_TOKEN und GITHUB_REPO in den Projekteigenschaften.');
  }

  const endpoint = 'https://api.github.com/repos/' + repo + '/issues?state=open&per_page=10';
  const response = UrlFetchApp.fetch(endpoint, {
    method: 'get',
    headers: {
      Authorization: 'token ' + token,
      'User-Agent': 'AppsScript-Archivator'
    },
    muteHttpExceptions: true
  });

  if (response.getResponseCode() !== 200) {
    throw new Error('GitHub-API Aufruf fehlgeschlagen: ' + response.getContentText());
  }

  const issues = JSON.parse(response.getContentText());
  const list = issues.map((issue) => ({
    number: issue.number,
    title: issue.title,
    url: issue.html_url
  }));

  const prompt = 'Fasse diese offenen GitHub-Issues auf Deutsch stichpunktartig zusammen:\n' +
    list.map((issue) => `#${issue.number}: ${issue.title}`).join('\n');
  const summary = askOpenAI(prompt);

  return { issues: list, summary: summary };
}

/**
 * Sends structured automation data to a Zapier webhook for further processing.
 * Configure ZAPIER_WEBHOOK_URL in Script Properties.
 * @param {Object} payload
 */
function postToZapier(payload) {
  const webhookUrl = getSecret('ZAPIER_WEBHOOK_URL');
  if (!webhookUrl) {
    throw new Error('Bitte hinterlege die Zapier-Webhook-URL in den Projekteigenschaften (ZAPIER_WEBHOOK_URL).');
  }

  UrlFetchApp.fetch(webhookUrl, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
}

/**
 * Runs the unified automation: collects daily insights and sends them to Zapier.
 * Combines calendar, mail, Drive, GitHub and sheet prompts.
 * @return {Object}
 */
function runAutomationHub() {
  const startSummary = startDay();
  const driveSummary = summarizeDriveFolder();
  const githubDigest = fetchGitHubDigest();
  const sheetResult = (() => {
    try {
      return processSheetPrompts();
    } catch (error) {
      Logger.log('Sheet processing skipped: %s', error.message);
      return { processed: 0, skipped: true, message: error.message };
    }
  })();

  const finalSummaryPrompt = [
    'Erstelle einen kompakten deutschen Tagesbericht aus diesen Informationen:',
    'Kalender/Mails: ' + JSON.stringify(startSummary),
    'Drive: ' + JSON.stringify(driveSummary),
    'GitHub: ' + JSON.stringify(githubDigest)
  ].join('\n');
  const assistantSummary = askOpenAI(finalSummaryPrompt);

  const payload = {
    generatedAt: new Date(),
    calendar: startSummary,
    drive: driveSummary,
    github: githubDigest,
    sheet: sheetResult,
    assistantSummary: assistantSummary
  };

  postToZapier(payload);
  return payload;
}
