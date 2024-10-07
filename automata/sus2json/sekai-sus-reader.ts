import SusAnalyzer, { type ISusNotes, type ISusScore } from "sus-analyzer";


interface Note {
  t: number;  // Absolute timestamp in milliseconds
  tid: number;  // Unique ID
  measure: number;
  tick: number;
  r: string;  // Raw type
  type: string;
  lane: number;  // NOT 0-indexed. The first lane is 2
  width?: number;
  slideId?: number;
  shortNote?: Note;
  airNote?: Note;
}

const pop = (obj: { [key: string]: Note }, key: string) => {
  let value = obj[key]
  if (value) delete obj[key]
  return value
}

export function read(sus: string): { taps: Note[]; slides: Note[][]; } {
  // Ref: https://github.com/PurplePalette/pjsekai-score-doc/wiki/%E4%BD%9C%E6%88%90%E6%96%B9%E6%B3%95
  const data: ISusScore = SusAnalyzer.getScore(sus, 480)

  // Calculate the starting milliseconds of each measure.
  let accumulator = 0
  const startMs = [0, ...data.BPMs.map((bpm, i) => Math.floor(accumulator += (60 / bpm * 1000) * data.BEATs[i]))]

  function calcTime(note: ISusNotes) {
    // To calculate the relative time from the start of the measure:
    // - We have 480 ticks per beat, so we do note.tick / 480 to get the number of beats.
    // - We do 60 / BPM * 1000 to get the milliseconds per beat.
    // - Multiply together to get the number of milliseconds.
    return Math.floor(startMs[note.measure] + (note.tick / 480) * (60 / data.BPMs[note.measure] * 1000))
  }

  const key = (note: Note | ISusNotes) => `${note.measure}_${note.tick}_${note.lane}`
  const attrs = (note: ISusNotes) => ({ t: calcTime(note),
    lane: note.lane, tick: note.tick, measure: note.measure, width: note.width, tid: 0
  })

  // use to remove overlapping tap + flick or tap + slide head
  let shortNotesMap: { [key: string]: Note } = Object.fromEntries(data.shortNotes
    .filter(note => note.lane >= 2 && note.lane <= 13)  // 0 is skill, 15 is fever, not useful :(
    .map(note => ({ type: ["unknown", "tap", "yellow tap", "diamond"][note.noteType], r: "short", ...attrs(note) }))
    .map(note => [key(note), note]))

  // Map airNote to slideNote
  const aTypes = ["unknown", "flick", "flick left", "flick right", "slide bend middle", "slide bend left", "slide bend right"]
  let airs: { [key: string]: Note } = Object.fromEntries(data.airNotes
    .map(note => ({ type: aTypes[note.noteType], r: "air", ...attrs(note), shortNote: pop(shortNotesMap, key(note)) }))
    .map(note => [key(note), note]))

  // Slide notes
  let tid = 0
  const sTypes = ["unknown", "slide head", "slide tail", "slide waypoint hvcombo", "unknown", "slide waypoint nocombo"]
  let slides: Note[][] = data.slideNotes.map(((notes, slideId) => notes
    .map(note => ({ type: sTypes[note.noteType], r: "slide", ...attrs(note), slideId,
      shortNote: pop(shortNotesMap, key(note)), airNote: pop(airs, key(note)) }))
    .toSorted((a, b) => a.t - b.t)))

  // Add to result, sort by time, and add a unique ID
  const taps = [...Object.values(shortNotesMap), ...Object.values(airs)]
    .sort((a, b) => a.t - b.t).map(it => ({...it, tid: tid++}))
  slides.forEach((slide) => { tid++; slide.forEach(note => note.tid = tid++) })

  return { taps, slides }
}