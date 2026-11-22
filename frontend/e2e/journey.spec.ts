/**
 * The whole first-time journey through the real UI, on fake data (Aisyah Tan, a "Contoh" company):
 * first-run checklist → profile → upload a fake resume and save the bank → import a job by smart paste →
 * score and verdict → "I have this" rescoring → save to tracker → Copy-Paste tailor with a saved fake AI reply
 * (flags visible, accept, save) → download PDF → mark as applied → Kanban shows it.
 */
import { expect, headerScore, JOB_AD, test } from './fixtures'
import { FAKE_RESUME } from '../playwright.config'

type BankItem = { code: string; title: string; type: string }

test.describe.configure({ mode: 'serial' })

test.beforeEach(async ({ page }) => {
  // The setup wizard is its own feature; these tests start from Today's first-run checklist.
  await page.addInitScript(() => localStorage.setItem('setupDone', '1'))
})

test('first-time journey: from an empty app to an application on the Kanban', async ({ page, request }) => {
  await test.step('Today shows the first-run checklist', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Get started in three steps' })).toBeVisible()
    await page.getByRole('link', { name: 'Open profile' }).click()
    await expect(page).toHaveURL(/section=profile/)
  })

  await test.step('fill in the profile', async () => {
    await page.getByLabel('Name').fill('Aisyah Tan')
    await page.getByLabel('Highest education').selectOption('Degree')
    await page.getByLabel('Field of study').fill('Software Engineering')
    await page.getByLabel('Languages you speak').fill('English, Bahasa Malaysia')
    await page.getByRole('button', { name: 'Save profile' }).click()
    await expect(page.getByText('Saved. Jobs rescored.')).toBeVisible()
  })

  await test.step('upload a fake resume and save the Experience Bank', async () => {
    await page.getByRole('link', { name: 'Resume', exact: true }).click()
    await page.locator('input[type="file"]').setInputFiles(FAKE_RESUME)
    const save = page.getByRole('button', { name: 'Save to Experience Bank' })
    await expect(save).toBeEnabled()
    await save.click()
    await expect(page.getByText('Software Engineering Intern').first()).toBeVisible()
  })

  let jobUrl = ''
  await test.step('import a job by smart paste and see its score and verdict', async () => {
    await page.getByRole('link', { name: 'Jobs', exact: true }).click()
    await page.getByRole('button', { name: 'Import job' }).click()
    await page.getByLabel('Paste the job page').fill(JOB_AD)
    await page.getByRole('button', { name: 'Read pasted text' }).click()
    await page.getByLabel('Job title').fill('Junior Software Engineer')
    await page.getByLabel('Company').fill('Syarikat Contoh Fintech Sdn Bhd')
    await page.getByRole('button', { name: 'Import and score' }).click()
    await expect(page).toHaveURL(/\/jobs\/\d+/)
    jobUrl = page.url()
    await expect(page.getByRole('heading', { name: 'Junior Software Engineer' })).toBeVisible()
    await expect(page.getByText(/^(Strong|Partial|Weak) match: .*required skills/)).toBeVisible()
    await expect(page.getByRole('heading', { name: /^You're missing|^Nothing missing$/ })).toBeVisible()
  })

  await test.step('"I have this" adds a missing skill and rescores at once', async () => {
    const before = await headerScore(page)
    page.once('dialog', (d) => d.accept()) // "Add HTML to your profile skills?"
    await page.getByRole('button', { name: 'I have HTML: add it to my profile skills' }).click()
    await expect(page.getByText('HTML added to your profile. Scores updated.')).toBeVisible()
    await expect.poll(() => headerScore(page)).toBeGreaterThan(before)
  })

  await test.step('save to tracker', async () => {
    await page.getByRole('button', { name: 'Save to tracker' }).click()
    await expect(page.getByRole('button', { name: 'Tailor resume' }).first()).toBeVisible()
  })

  await test.step('Copy-Paste tailor: paste a saved fake AI reply, see the flags, accept, save', async () => {
    const bank: BankItem[] = await (await request.get('/api/experience')).json()
    const work = bank.find((b) => b.type === 'work')!
    const project = bank.find((b) => b.type === 'project')!
    const reply = '```json\n' + JSON.stringify({
      summary: 'Software engineering graduate who builds React dashboards and Python APIs.',
      skills_order: ['Python', 'React', 'Kubernetes'],
      sections: [
        { section: 'Experience', items: [
          { source_id: work.code, text: 'Wrote REST APIs in Python (FastAPI) backed by PostgreSQL' },
          { source_id: work.code, text: 'Built internal dashboards with React and TypeScript' },
          { source_id: 'B99', text: 'Led a team of 8 engineers at a bank' },
        ] },
        { section: 'Projects', items: [
          { source_id: project.code, text: 'Flutter app with Firebase authentication, shipped with Docker' },
        ] },
      ],
      omitted_ids: [], notes: 'Kubernetes is not in the bank.',
    }, null, 2) + '\n```'

    await page.locator('header').getByRole('button', { name: 'Tailor resume' }).click()
    // The imported resume is a base resume, so tailoring asks where to start; nothing used yet = the whole bank.
    await expect(page.getByLabel('Start from')).toHaveValue('')
    await page.getByRole('button', { name: 'Build prompt' }).click()
    await page.getByPlaceholder("Paste the chat's reply here", { exact: false }).fill(reply)
    await page.getByRole('button', { name: 'Check reply' }).click()
    await expect(page.getByText(/flagged in red: possibly invented/)).toBeVisible() // B99, Kubernetes
    await expect(page.getByText(/in amber: worth a look/)).toBeVisible() // Docker isn't in the project item
    await expect(page.getByText('No bank item “B99”: nothing to compare with.')).toBeVisible()
    await expect(page.getByText(`Docker isn't in ${project.code}`, { exact: false })).toBeVisible()
    await page.getByRole('button', { name: 'Save as new resume version' }).click()
    await expect(page.getByText(/Saved as\s*Resume v1/)).toBeVisible()
    await page.getByRole('button', { name: 'Close' }).first().click()
  })

  await test.step('download the PDF, then mark as applied', async () => {
    await page.goto(jobUrl)
    const download = page.locator('header').getByRole('link', { name: 'Download resume v1' })
    const href = await download.getAttribute('href')
    const pdf = await request.get(href!)
    expect(pdf.headers()['content-type']).toContain('application/pdf')
    expect((await pdf.body()).subarray(0, 5).toString()).toBe('%PDF-')
    const docx = await request.get(href!.replace(/pdf$/, 'docx'))
    expect(docx.headers()['content-type']).toContain('wordprocessingml')
    expect((await docx.body()).subarray(0, 2).toString()).toBe('PK') // a .docx is a zip
    const popup = page.waitForEvent('popup')
    await download.click() // opens the PDF in a new tab and moves the job to its next step
    await (await popup).close()
    await page.getByRole('button', { name: 'Mark as applied' }).click()
    await expect(page.locator('header').getByText('Applied', { exact: true })).toBeVisible()
  })

  await test.step('the Kanban shows it under Applied', async () => {
    await page.getByRole('link', { name: 'Tracker', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Applied column' }).getByText('Junior Software Engineer')).toBeVisible()
    await expect(page.getByRole('region', { name: 'Saved column' }).getByText('Junior Software Engineer')).toHaveCount(0)
  })
})

test('hide with undo, and snoozing a next step', async ({ page, request }) => {
  const jobs: { id: number; title: string }[] = await (await request.get('/api/jobs')).json()
  const job = jobs.find((j) => j.title === 'Junior Software Engineer')!

  await test.step('Hide then Undo puts the job back', async () => {
    await page.goto(`/jobs/${job.id}`)
    await page.getByRole('button', { name: 'Hide', exact: true }).click()
    await expect(page.getByText('Job hidden.')).toBeVisible()
    await page.getByRole('status').getByRole('button', { name: 'Undo' }).click()
    await expect.poll(async () => (await (await request.get(`/api/jobs/${job.id}`)).json()).job.hidden).toBe(false)
  })

  await test.step('snooze a next step on Today', async () => {
    await page.goto('/')
    const steps = page.getByRole('list').filter({ has: page.getByRole('button', { name: /^Snooze for 3 days:/ }) })
    const first = steps.getByRole('listitem').first()
    const text = (await first.innerText()).split('\n')[0]
    await first.getByRole('button', { name: /^Snooze for 3 days:/ }).click()
    await expect(page.getByText('Snoozed for 3 days.')).toBeVisible()
    await expect(page.getByRole('listitem').filter({ hasText: text })).toHaveCount(0)
  })
})

test('the reorganised editors: base resumes, run log, skill dictionary, location map', async ({ page, request }) => {
  await test.step('base resumes: create, pick a whole group, duplicate, rename, delete with undo', async () => {
    await page.goto('/resume')
    const section = page.getByRole('region', { name: 'Base resumes' })
    await expect(section.getByText('A base resume is a starting set of bank items')).toBeVisible()
    await section.getByRole('button', { name: 'New base resume' }).click()
    await section.getByRole('textbox', { name: 'Name for the new base resume' }).fill('IT support')
    await section.getByRole('button', { name: 'Create' }).click()
    // the editor opens on the new, empty selection
    await expect(section.getByText(/^0 of \d+ items selected/)).toBeVisible()
    await section.getByRole('checkbox', { name: 'Select all in Education' }).check()
    await expect(section.getByText(/^[1-9]\d* of \d+ items selected/)).toBeVisible()
    await section.getByRole('searchbox', { name: 'Search bank items' }).fill('zzz-nothing')
    await expect(section.getByText('No items match “zzz-nothing”.')).toBeVisible()
    await section.getByRole('button', { name: 'Save', exact: true }).click()
    const row = section.getByRole('listitem').filter({ hasText: 'IT support' })
    await expect(row.getByText(/^\d+ education$/)).toBeVisible()

    await row.getByRole('button', { name: 'Duplicate IT support' }).click()
    await expect(section.getByText('IT support (copy)')).toBeVisible()
    await section.getByRole('button', { name: 'Rename IT support (copy)' }).click()
    await section.getByRole('textbox', { name: 'New name for IT support (copy)' }).fill('Helpdesk')
    await section.getByRole('button', { name: 'Save name' }).click()
    await expect(section.getByText('Helpdesk', { exact: true })).toBeVisible()

    await section.getByRole('button', { name: 'Delete Helpdesk' }).click()
    await expect(section.getByText('Helpdesk', { exact: true })).toHaveCount(0)
    await page.getByRole('status').getByRole('button', { name: 'Undo' }).click()
    await expect(section.getByText('Helpdesk', { exact: true })).toBeVisible()
    const names = (await (await request.get('/api/resumes')).json()).map((r: { name: string }) => r.name)
    expect(names).toEqual(expect.arrayContaining(['IT support', 'Helpdesk']))
  })

  await test.step('tailor from a base resume: only its items in the prompt, the rest offered in the review, last used', async () => {
    const bank: BankItem[] = await (await request.get('/api/experience')).json()
    const edu = bank.find((b) => b.type === 'education')!
    const work = bank.find((b) => b.type === 'work')!
    const apps: { job_id: number }[] = await (await request.get('/api/applications')).json()
    await page.goto(`/jobs/${apps[0].job_id}`)
    await page.getByRole('button', { name: 'More' }).click()
    await page.getByRole('button', { name: 'Tailor resume (new version)' }).click()
    await page.getByLabel('Start from').selectOption({ label: 'IT support' })
    await expect(page.getByText(/^Only IT support's \d+ items go to the AI/)).toBeVisible()
    const created = page.waitForResponse((r) => r.url().endsWith('/api/ai/tasks') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Build prompt' }).click()
    const task = await (await created).json()
    expect(task.base_resume_id).toBeTruthy()
    expect(task.prompt).toContain(`[${edu.code}] education:`)
    expect(task.prompt).not.toContain(`[${work.code}]`)

    const reply = '```json\n' + JSON.stringify({
      summary: 'Software engineering student with a strong academic record.', skills_order: [],
      sections: [{ section: 'Education', items: [{ source_id: edu.code, text: edu.title }] }], omitted_ids: [], notes: '',
    }) + '\n```'
    await page.getByPlaceholder("Paste the chat's reply here", { exact: false }).fill(reply)
    await page.getByRole('button', { name: 'Check reply' }).click()
    await expect(page.getByRole('heading', { name: /^Other bank items/ })).toBeVisible()
    await expect(page.getByRole('checkbox', { name: new RegExp(work.title) })).toBeVisible() // can still be ticked in
    await page.keyboard.press('Escape')

    await page.goto('/resume')
    const row = page.getByRole('region', { name: 'Base resumes' }).getByRole('listitem').filter({ hasText: /^IT support/ })
    await expect(row.getByText('Never')).toHaveCount(0) // Last used is now a date
    await page.goto(`/jobs/${apps[0].job_id}`)
    await page.getByRole('button', { name: 'More' }).click()
    await page.getByRole('button', { name: 'Tailor resume (new version)' }).click()
    await expect(page.getByLabel('Start from')).toHaveValue(String(task.base_resume_id)) // the last one used is the default
    await page.keyboard.press('Escape')
  })

  await test.step('run log: one row per source with aligned numbers, filter and details', async () => {
    await request.post('/api/automations/fetch_jobs/run') // offline: the E2E servers replay saved fixtures
    await expect.poll(async () => {
      const runs = await (await request.get('/api/automations/runs?limit=5')).json()
      return runs.find((r: { automation_key: string }) => r.automation_key === 'fetch_jobs')?.result
    }, { timeout: 30_000 }).not.toBe('running')
    await page.goto('/automations')
    const log = page.getByRole('region', { name: 'Run log' })
    await expect(log.getByRole('columnheader', { name: 'Requests' })).toBeVisible()
    await expect(log.getByRole('row').filter({ hasText: 'JobStreet' }).first()).toBeVisible()
    await log.getByRole('combobox', { name: 'Show runs of' }).selectOption({ label: 'JobStreet' })
    const rows = log.getByRole('row').filter({ has: page.getByRole('cell') })
    for (const text of await rows.allInnerTexts()) expect(text).toContain('JobStreet')
  })

  await test.step('skill dictionary: search an alias, edit in the side panel with alias chips', async () => {
    await page.goto('/settings?section=skills')
    await page.getByRole('searchbox', { name: 'Search skills and aliases' }).fill('reactjs')
    await page.getByRole('button', { name: 'Edit React', exact: true }).click()
    const panel = page.getByRole('complementary', { name: 'Edit React' })
    await panel.getByRole('textbox', { name: 'Other names for it' }).fill('React 19')
    await page.keyboard.press('Enter')
    await expect(panel.getByRole('button', { name: 'Remove React 19' })).toBeVisible()
    await panel.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByText('Saved React. Jobs rescored.')).toBeVisible()
    const skills: { name: string; aliases: string[] }[] = await (await request.get('/api/skills')).json()
    expect(skills.find((s) => s.name === 'React')!.aliases).toContain('React 19')
    await page.getByRole('searchbox', { name: 'Search skills and aliases' }).fill('')
    await page.getByRole('button', { name: 'Category' }).click()
    await expect(page.getByRole('columnheader', { name: 'Category' })).toHaveAttribute('aria-sort', 'ascending')
  })

  await test.step('location map: find a town in two states, add with duplicate check, remove with undo, save', async () => {
    await page.goto('/settings?section=location-map')
    await page.getByRole('searchbox', { name: 'Find a town or area' }).fill('Cheras')
    await expect(page.getByText(/^Found in .*Selangor/)).toContainText('Kuala Lumpur')
    const add = page.getByRole('textbox', { name: 'Add a town or area to Selangor' })
    await add.fill('cheras')
    await add.press('Enter')
    await expect(page.getByRole('alert')).toHaveText('cheras is already in Selangor.')
    await add.fill('Taman Contoh')
    await add.press('Enter')
    const towns = page.getByRole('list', { name: 'Towns in Selangor' })
    await expect(towns.getByText('Taman Contoh')).toBeVisible()
    await towns.getByRole('button', { name: 'Remove Taman Contoh from Selangor' }).click()
    await expect(towns.getByText('Taman Contoh')).toHaveCount(0)
    await page.getByRole('status').getByRole('button', { name: 'Undo' }).click()
    await expect(towns.getByText('Taman Contoh')).toBeVisible()
    await page.getByRole('button', { name: 'Save and rescore' }).click()
    await expect(page.getByText('Location map saved. Jobs rescored.')).toBeVisible()
    const settings = await (await request.get('/api/settings')).json()
    expect(settings.locations.Selangor).toContain('Taman Contoh')
  })
})
