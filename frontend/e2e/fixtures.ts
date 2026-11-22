import { test as base, expect, type Page } from '@playwright/test'

/** Every page: only this laptop may be contacted. Anything else (fonts, analytics, a job site) is aborted and counted. */
export const test = base.extend<{ localOnly: string[] }>({
  localOnly: [async ({ context }, use) => {
    const blocked: string[] = []
    await context.route('**/*', (route) => {
      const url = route.request().url()
      if (/^(https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/|data:|blob:)/.test(url)) return route.continue()
      blocked.push(url)
      return route.abort()
    })
    await use(blocked)
    expect(blocked, 'requests that tried to leave this laptop').toEqual([])
  }, { auto: true }],
})

export { expect }

/** The job's quick score as shown in the big badge on Job Detail. */
export async function headerScore(page: Page): Promise<number> {
  const text = await page.locator('header').getByText(/^~?\d+$/).first().innerText()
  return Number(text.replace('~', ''))
}

export const JOB_AD = `Junior Software Engineer
Syarikat Contoh Fintech Sdn Bhd
Kuala Lumpur
Full time

About the role
You will build and maintain web services for our payments platform.

Requirements:
- Degree in Computer Science, Software Engineering or related field
- Fresh graduates are welcome
- Good knowledge of Python and SQL
- Experience with React and HTML
- Familiar with Git

Nice to have:
- Docker
- Good command of English`
