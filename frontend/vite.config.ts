import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({base:process.env.GITHUB_ACTIONS?'/supply-chain-skills-lab/':'/',plugins:[react()],server:{port:5187,strictPort:true}});
