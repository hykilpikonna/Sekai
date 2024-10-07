import SusAnalyzer from "sus-analyzer";
import * as fs from "node:fs";
import { read } from "./sekai-sus-reader.ts";
import SekaiSusReader from './sekai-sus-reader-old'

const a = read(fs.readFileSync('./expert.txt', 'utf8'))
fs.writeFileSync('./expert-new.json', JSON.stringify(a, null, 2))

const b = SekaiSusReader.Read(fs.readFileSync('./expert.txt', 'utf8'))
fs.writeFileSync('./expert-old.json', JSON.stringify(b, null, 2))

const c = SusAnalyzer.getScore(fs.readFileSync('./expert.txt', 'utf8'), 480)
fs.writeFileSync('./expert-sus.json', JSON.stringify(c, null, 2))