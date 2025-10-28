/**
 * Google Apps Script orchestrator for Dortmund City Sandbox CI/CD.
 */
const CONFIG = {
  repo: 'dortmund-city-sandbox',
  owner: 'Zweeback',
  githubApi: 'https://api.github.com',
  defaultBranch: 'work',
  discordWebhookProperty: 'DISCORD_WEBHOOK_URL'
};

/**
 * Creates the GitHub repository if it does not yet exist.
 * Requires a Script Property `GITHUB_TOKEN` with repo scope.
 */
function bootstrapRepository() {
  const token = getSecret('GITHUB_TOKEN');
  if (!token) {
    throw new Error('Missing GitHub token in script properties.');
  }

  const url = `${CONFIG.githubApi}/user/repos`;
  const payload = {
    name: CONFIG.repo,
    description: 'Unity-based Dortmund sandbox with GameCI automation.',
    homepage: 'https://zweeback.github.io/dortmund-city-sandbox',
    private: false
  };

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json' },
    muteHttpExceptions: true,
    payload: JSON.stringify(payload)
  });

  const code = response.getResponseCode();
  if (code === 201 || code === 422) {
    Logger.log('Repository ensured (status %s).', code);
    return JSON.parse(response.getContentText());
  }

  throw new Error(`Failed to create repository: ${response.getContentText()}`);
}

/**
 * Configures required secrets for GameCI workflows via GitHub REST API.
 * The `encryptSecret` helper expects libsodium sealed box support. Replace the
 * placeholder implementation with a production-ready variant (e.g. via
 * https://github.com/ageron/libsodium-apps-script).
 */
function configureSecrets(secrets) {
  const token = getSecret('GITHUB_TOKEN');
  if (!token) {
    throw new Error('Missing GitHub token in script properties.');
  }

  const url = `${CONFIG.githubApi}/repos/${CONFIG.owner}/${CONFIG.repo}/actions/secrets/public-key`;
  const keyResponse = UrlFetchApp.fetch(url, {
    headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json' }
  });
  const body = JSON.parse(keyResponse.getContentText());
  const publicKey = body.key;
  const keyId = body.key_id;

  secrets.forEach((secret) => {
    const encrypted = encryptSecret(publicKey, secret.value);
    const updateUrl = `${CONFIG.githubApi}/repos/${CONFIG.owner}/${CONFIG.repo}/actions/secrets/${secret.name}`;
    UrlFetchApp.fetch(updateUrl, {
      method: 'put',
      contentType: 'application/json',
      headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json' },
      payload: JSON.stringify({ encrypted_value: encrypted, key_id: keyId })
    });
    Logger.log('Secret %s updated.', secret.name);
  });
}

/**
 * Uses GitHub workflow dispatch to trigger a CI build.
 */
function triggerBuild(workflow) {
  const token = getSecret('GITHUB_TOKEN');
  if (!token) {
    throw new Error('Missing GitHub token in script properties.');
  }

  const url = `${CONFIG.githubApi}/repos/${CONFIG.owner}/${CONFIG.repo}/actions/workflows/${workflow}/dispatches`;
  const payload = { ref: CONFIG.defaultBranch };
  UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify(payload)
  });
  Logger.log('Workflow %s dispatched.', workflow);
}

/**
 * Posts a notification to Discord when a release is published.
 */
function notifyRelease(version, url) {
  const webhook = getSecret(CONFIG.discordWebhookProperty);
  if (!webhook) {
    Logger.log('No Discord webhook configured. Skipping notification.');
    return;
  }

  const payload = {
    content: `🚀 Dortmund City Sandbox ${version} ist verfügbar: ${url}`
  };

  UrlFetchApp.fetch(webhook, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload)
  });
}

/**
 * Retrieves a secret from script properties.
 */
function getSecret(name) {
  return PropertiesService.getScriptProperties().getProperty(name);
}

/**
 * Placeholder implementation for GitHub sealed box encryption.
 * Replace with a libsodium-based encoder before using in production.
 */
function encryptSecret(base64PublicKey, value) {
  Logger.log('encryptSecret called for %s (placeholder implementation).', base64PublicKey.substring(0, 6));
  return Utilities.base64Encode(Utilities.newBlob(value).getBytes());
}
