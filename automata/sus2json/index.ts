import SusAnalyzer from 'sus-analyzer'
import { readFileSync, writeFileSync } from 'fs'

// const preprocessChart = (chart: string) => {
//   // BPM定義を削除
//   chart = chart.replace(/#BPM.*/g, "");
//   // BPM変化を削除
//   chart = chart.replace(/#\d+08:.*/g, "");
//   //const newChart = chart.replace(/#(([1-9][0-9][0-9])|([0-9][1-9][0-9])|([0-9][0-9][1-9]))(08):(.*)/g, "").replace(/#(BPM)([0-9][2-9]):(.*)/g, "");
//   return chart;
// }

let sus = readFileSync('expert.txt', 'utf8')
// sus = preprocessChart(sus)
const score = SusAnalyzer.getScore(sus, 480)

// Dump score to json
writeFileSync('expert.json', JSON.stringify(score, null, 2))

import SekaiSusReader from './sekai-sus-reader'

const out = SekaiSusReader.Read(sus)
writeFileSync('expert-parsed.json', JSON.stringify(out, null, 2))
