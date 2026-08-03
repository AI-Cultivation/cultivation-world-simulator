const path = require('node:path')

const fs = require('node:fs')

const backendDir = process.env.CWS_DESKTOP_BACKEND_DIR
  ? path.resolve(process.env.CWS_DESKTOP_BACKEND_DIR)
  : path.resolve(__dirname, '..', 'tmp', 'desktop_backend')

const extraResources = [
  {
    from: backendDir,
    to: 'backend',
  },
]

if (process.env.CWS_DESKTOP_SEED_FILE && fs.existsSync(process.env.CWS_DESKTOP_SEED_FILE)) {
  extraResources.push({
    from: path.resolve(process.env.CWS_DESKTOP_SEED_FILE),
    to: 'desktop-seed.json',
  })
}

if (process.env.CWS_DESKTOP_DISTRIBUTION_MANIFEST && fs.existsSync(process.env.CWS_DESKTOP_DISTRIBUTION_MANIFEST)) {
  extraResources.push({
    from: path.resolve(process.env.CWS_DESKTOP_DISTRIBUTION_MANIFEST),
    to: 'desktop-distribution.json',
  })
}

if (process.env.CWS_DESKTOP_EOS_RUNTIME_FILE && fs.existsSync(process.env.CWS_DESKTOP_EOS_RUNTIME_FILE)) {
  extraResources.push({
    from: path.resolve(process.env.CWS_DESKTOP_EOS_RUNTIME_FILE),
    to: 'eos-runtime.json',
  })
}

if (process.env.CWS_DESKTOP_EOS_HELPER_DIR && fs.existsSync(process.env.CWS_DESKTOP_EOS_HELPER_DIR)) {
  extraResources.push({
    from: path.resolve(process.env.CWS_DESKTOP_EOS_HELPER_DIR),
    to: 'eos-helper',
  })
}

module.exports = {
  appId: 'com.cultivationworld.simulator',
  productName: 'CultivationWorldSimulator',
  directories: {
    output: 'release',
  },
  files: [
    'build/**/*',
    'package.json',
  ],
  asar: true,
  electronLanguages: ['zh-CN', 'zh-TW', 'en-US', 'ja', 'fr', 'vi'],
  extraResources,
  win: {
    signAndEditExecutable: false,
    forceCodeSigning: false,
    target: [
      {
        target: 'dir',
        arch: ['x64'],
      },
    ],
    icon: '../assets/icon.ico',
  },
}
