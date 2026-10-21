import { chromium } from 'playwright';
import path from 'path';

const OUT_DIR = 'C:/Users/Abhay/.gemini/antigravity-ide/brain/b7688548-476b-4567-823c-e3cf7d182162';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  console.log('Navigating to http://localhost:5173 ...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);

  // Screenshot 1: Landing page
  await page.screenshot({ path: `${OUT_DIR}/shot1_landing.png`, fullPage: true });
  console.log('Shot 1: Landing page captured');

  // Select demo-flask from dropdown
  await page.selectOption('select', 'demo-flask');
  console.log('Selected demo-flask scenario');
  await page.waitForTimeout(2000);

  // Screenshot 2: Pipeline starting
  await page.screenshot({ path: `${OUT_DIR}/shot2_pipeline_start.png`, fullPage: true });
  console.log('Shot 2: Pipeline starting');

  // Wait for demo to progress
  await page.waitForTimeout(6000);

  // Screenshot 3: Mid-run
  await page.screenshot({ path: `${OUT_DIR}/shot3_pipeline_running.png`, fullPage: true });
  console.log('Shot 3: Pipeline running');

  // Wait for completion
  await page.waitForTimeout(10000);

  // Screenshot 4: Completed state
  await page.screenshot({ path: `${OUT_DIR}/shot4_complete.png`, fullPage: true });
  console.log('Shot 4: Pipeline complete');

  // Switch to Sandbox Logs tab
  const logsTab = page.getByText('Sandbox Logs');
  if (await logsTab.isVisible()) {
    await logsTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${OUT_DIR}/shot5_logs.png`, fullPage: true });
    console.log('Shot 5: Sandbox logs tab');
  }

  // Switch to RCA Diagnosis tab
  const diagnosisTab = page.getByText('RCA Diagnosis');
  if (await diagnosisTab.isVisible()) {
    await diagnosisTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${OUT_DIR}/shot6_diagnosis.png`, fullPage: true });
    console.log('Shot 6: RCA diagnosis tab');
  }

  await browser.close();
  console.log('All screenshots saved!');
})();
