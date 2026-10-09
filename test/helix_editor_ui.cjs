// Run with Playwright installed; optionally pass a JSON environment/sample fixture.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=process.argv[2]?JSON.parse(fs.readFileSync(process.argv[2],'utf8')):JSON.parse(execFileSync(
  process.env.PYTHON_EXECUTABLE||path.join(root,'.venv/bin/python'),['-c',`
import json, tempfile, base64
from pathlib import Path
from features.helix.helix_service import HelixService
from features.helix.helix_excel import build_excel_template
with tempfile.TemporaryDirectory() as directory:
    service = HelixService(Path(directory) / 'helix.sqlite3')
    source = json.loads(Path('reference/Service with questions.json').read_text())
    environment = service.save_environment('UI test', source)
    sample = service.sample_service(environment['id'])
    print(json.dumps({'environment': service.get_environment(environment['id']), 'sample': sample,
                      'sampleExcel': base64.b64encode(build_excel_template(source, sample)).decode()}))
`],{cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'src')},encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];let saved;
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://helix.test/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/helix/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'pages/helix.html'),'utf8')});
   if(url.pathname==='/helix/question-editor.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'pages/helix-question-editor.js'),'utf8')});
   if(url.pathname.endsWith('/excel-sample')&&fixture.sampleExcel)return route.fulfill({contentType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',body:Buffer.from(fixture.sampleExcel,'base64')});
   let data=fixture.environment;
   if(url.pathname.endsWith('/environments'))data=[fixture.environment];
   if(url.pathname.endsWith('/sample-service'))data=fixture.sample;
   if(url.pathname.endsWith('/packages')){saved=route.request().postDataJSON();data={id:'test-package',createdAt:new Date().toISOString(),names:saved.services.map(s=>s.name),tags:[]};}
   await route.fulfill({json:{success:true,data}});
  });
  await page.goto('http://helix.test/helix/#'+fixture.environment.id);
  await page.locator('#detail').waitFor({state:'visible'});
  if(fixture.sampleExcel){const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download Excel sample',exact:true}).click();const download=await downloadPromise;assert.equal(download.suggestedFilename(),'Helix-services-sample.xlsx');await download.saveAs('/tmp/helix-browser-sample.xlsx');}
  await page.locator('#load-sample').click();
  await page.waitForFunction(()=>document.querySelector('#question-count').textContent==='17 questions');
  const untouched=await page.evaluate(()=>collectQuestions());
  for(const q of untouched){const original=fixture.sample.questions.find(x=>x.id===q.id);assert.deepEqual(q.config,original.config);}
  const tableSpec=fixture.sample.questions.find(q=>q.type==='DataTable');
  const card=page.locator(`[data-question-id="${tableSpec.id}"]`);
  await card.locator(':scope > summary').click();
  await card.getByRole('textbox',{name:'Column title'}).first().fill('Employee');
  await card.getByRole('textbox',{name:'Row 1, Column 1',exact:true}).fill('Alice');
  await card.getByRole('button',{name:'+ Add column',exact:true}).click();
  await card.getByRole('textbox',{name:'Column title'}).last().fill('Notes');
  await card.getByRole('button',{name:'+ Add row',exact:true}).click();
  await card.getByRole('textbox',{name:'Row 3, Employee',exact:true}).fill('Bob');
  await card.getByRole('textbox',{name:'Row 3, Notes',exact:true}).fill('New row');
  await card.getByRole('radio',{name:'Default row 3',exact:true}).check();
  const radioSpec=fixture.sample.questions.find(q=>q.type==='RadioButtons');const radio=page.locator(`[data-question-id="${radioSpec.id}"]`);
  await radio.locator(':scope > summary').click();
  await radio.getByRole('textbox',{name:'Choice label',exact:true}).first().fill('First option');
  await radio.getByRole('textbox',{name:'Saved choice value',exact:true}).first().fill('first');
  await radio.getByRole('button',{name:'+ Add choice',exact:true}).click();
  await radio.locator('summary').filter({hasText:'Visibility conditions'}).click();
  await radio.getByLabel('Comparison',{exact:true}).selectOption('EQUALS');
  await radio.getByLabel('Expected saved value(s)',{exact:true}).fill('Edited default');
  await radio.getByRole('button',{name:'+ Combine condition',exact:true}).click();
  assert.equal(await radio.getByLabel('Match',{exact:true}).inputValue(),'AND');
  await radio.getByRole('button',{name:'Remove condition',exact:true}).last().click();
  await card.getByRole('button',{name:'+ Add column',exact:true}).click();
  await card.getByRole('button',{name:'Remove column',exact:true}).last().click();
  await card.getByRole('button',{name:'+ Add row',exact:true}).click();
  await card.getByRole('button',{name:'Remove row',exact:true}).last().click();
  const groupSpec=fixture.sample.questions.find(q=>q.type==='RepeatableGroup');const group=page.locator(`[data-question-id="${groupSpec.id}"]`);
  await group.locator(':scope > summary').click();
  await group.getByRole('button',{name:'+ Add group question',exact:true}).click();
  const child=group.locator('.group-questions > .question-card').last();
  await child.getByLabel('Question label',{exact:true}).fill('Group choice');
  await child.getByLabel('Answer type').selectOption('Dropdown');
  await child.getByRole('button',{name:'+ Add choice',exact:true}).click();
  const short=fixture.sample.questions.find(q=>q.type==='TextField'&&!q.config.hidden&&!q.config.readOnly);const textCard=page.locator(`[data-question-id="${short.id}"]`);
  await textCard.locator(':scope > summary').click();await textCard.getByLabel('Default answer',{exact:true}).fill('Edited default');
  await page.locator('#generate').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-edit]').length===1);
  await page.locator('[data-edit="0"]').click();
  assert.equal(await page.locator('#save-package').isDisabled(),true);
  const collected=await page.evaluate(()=>collectQuestions());const editedTable=collected.find(q=>q.id===tableSpec.id).config.questionMultiColumn;
  assert.equal(editedTable.metaData[0].displayName,'Employee');assert.equal(editedTable.data[0].displayValue[0],'Alice');assert.equal(editedTable.metaData.length,5);assert.equal(editedTable.data.length,3);assert.equal(editedTable.data[2].displayValue[4],'New row');
  assert.equal(collected.find(q=>q.id===short.id).config.defaultAnswer,'Edited default');
  assert.equal(collected.find(q=>q.id===radioSpec.id).config.options[0].dataValue,'first');
  assert.equal(collected.find(q=>q.id===radioSpec.id).config.visibilityCondition.expression.operator,'EQUALS');
  assert.equal(collected.find(q=>q.id===radioSpec.id).config.visibilityCondition.expression.right.value,'Edited default');
  assert.equal(collected.find(q=>q.id===groupSpec.id).pageItems[2].type,'Dropdown');
  await page.locator('#service-name').fill('Edited sample');await page.locator('#generate').click();await page.locator('#save-package').click();
  await page.waitForFunction(()=>document.querySelector('#packages').textContent.includes('Edited sample'));
  assert.equal(saved.services.length,1);assert.equal(saved.services[0].name,'Edited sample');
  fs.writeFileSync('/tmp/helix-edited-ui-payload.json',JSON.stringify(saved));
  await page.locator('#load-sample').click();await page.waitForFunction(()=>document.querySelector('#question-count').textContent==='17 questions');
  await page.screenshot({path:'/tmp/helix-studio-desktop.png',fullPage:true});
  await card.locator(':scope > summary').click();await card.scrollIntoViewIfNeeded();await page.screenshot({path:'/tmp/helix-studio-table.png'});
  await card.locator(':scope > summary').click();
  await page.setViewportSize({width:390,height:844});await card.locator(':scope > summary').click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.screenshot({path:'/tmp/helix-studio-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('Passed: sample fidelity, table edits, choices, nested groups, defaults, draft edit/save, mobile layout.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
