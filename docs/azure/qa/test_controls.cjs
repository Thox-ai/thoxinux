const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..');
function button(){return {listeners:{},attrs:{},textContent:'',addEventListener(k,f){this.listeners[k]=f;},setAttribute(k,v){this.attrs[k]=v;}};}
const theme=button(),print=button(),document={documentElement:{dataset:{theme:'light'}},querySelector(selector){return selector==='[data-theme-toggle]'?theme:selector==='[data-print]'?print:null;},querySelectorAll(){return [];}};
let printed=0;const context={document,window:{print(){printed++;}},Array,String,Math};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'html/thox-report.js'),'utf8'),context);
theme.listeners.click();assert.equal(document.documentElement.dataset.theme,'dark');assert.equal(theme.attrs['aria-pressed'],'true');assert.equal(theme.textContent,'Light view');
theme.listeners.click();assert.equal(document.documentElement.dataset.theme,'light');assert.equal(theme.attrs['aria-pressed'],'false');assert.equal(theme.textContent,'Dark view');
print.listeners.click();assert.equal(printed,1);
const result={scope:'isolated control fixture; not a browser layout or print-CSS test',theme_toggle:'passed both directions with ARIA state',print_control:'passed window.print dispatch'};
fs.writeFileSync(path.join(__dirname,'control-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
