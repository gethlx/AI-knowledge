import {defineConfig} from 'vite';
import {readFileSync} from 'node:fs';

export default defineConfig({
  base:'./',
  build:{outDir:'dist-ui'},
  plugins:[{
    name:'atlas-legacy-entry',
    generateBundle(){
      this.emitFile({type:'asset',fileName:'atlas.html',source:readFileSync(new URL('./atlas.html',import.meta.url),'utf8')});
    }
  }]
});
