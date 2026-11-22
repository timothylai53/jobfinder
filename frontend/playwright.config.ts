/**
 * End-to-end tests: the real backend + the real UI, driven by Chromium, on FAKE data only.
 *
 * - Own ports (API 8740, UI 5740), so a running JobFinder (8730/5730) is never touched.
 * - Own throwaway data folder (e2e_data/, gitignored), wiped at the start of every run: the real data/jobfinder.db
 *   is never opened. No scheduler, offline fake job sources, no automatic backup.
 * - Every browser request that isn't to 127.0.0.1/localhost is aborted (see e2e/fixtures.ts).
 */
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

const ROOT = path.resolve(import.meta.dirname, '..')
const BACKEND = path.join(ROOT, 'backend')
export const E2E_DATA = path.join(ROOT, 'e2e_data')
export const FAKE_RESUME = path.join(E2E_DATA, 'aisyah-tan-fake-resume.docx')
const API = 8740
const UI = 5740

// The backend's Python: the project venv locally, the job's own Python in CI (or E2E_PYTHON).
const venv = path.join(BACKEND, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const PYTHON = process.env.E2E_PYTHON ?? (existsSync(venv) ? venv : 'python')

// Runs once in the main process (workers inherit E2E_PREPARED): a clean data folder and the fake resume file,
// made by the same generator the backend tests use.
if (!process.env.E2E_PREPARED) {
  rmSync(E2E_DATA, { recursive: true, force: true })
  mkdirSync(E2E_DATA, { recursive: true })
  execFileSync(PYTHON, ['-c', `from pathlib import Path; from tests.fixtures.make_files import make_docx; make_docx(Path(r"${FAKE_RESUME}"))`],
    { cwd: BACKEND, stdio: 'inherit' })
  process.env.E2E_PREPARED = '1'
}

const backendEnv = {
  JOBFINDER_DATA_DIR: E2E_DATA,
  JOBFINDER_TEMPLATES_DIR: path.join(E2E_DATA, 'prompt-templates'),
  JOBFINDER_NO_SCHEDULER: '1',
  JOBFINDER_FAKE_SOURCES: '1',
  JOBFINDER_NO_AUTO_BACKUP: '1',
  JOBFINDER_FRONTEND_ORIGINS: `http://127.0.0.1:${UI},http://localhost:${UI}`,
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // one shared database: the journey is a single ordered story
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${UI}`,
    ...devices['Desktop Chrome'],
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn app.main:app --host 127.0.0.1 --port ${API}`,
      cwd: BACKEND,
      url: `http://127.0.0.1:${API}/api/health`,
      env: backendEnv,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${UI} --strictPort`,
      cwd: import.meta.dirname,
      url: `http://127.0.0.1:${UI}`,
      env: { JOBFINDER_API: `http://127.0.0.1:${API}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
