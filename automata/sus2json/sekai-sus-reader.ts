import SusAnalyzer, { type ISusNotes, type ISusScore } from "sus-analyzer";


interface Note {
  t: number;  // Absolute timestamp in milliseconds
  measure: number;
  tick: number;
  r: string;  // Raw type
  type: string;
  lane: number;  // NOT 0-indexed. The first lane is 2
  width?: number;
  slideId?: number;
  shortNote?: Note;
  airNote?: Note;
  diamondNote?: Note;
}


export function read(sus: string): { timestampNotes: Note[]; slides: Note[][]; } {
  // score files source: https://pjsek.ai/assets/startapp/music/music_score
  // ref: https://github.com/PurplePalette/pjsekai-score-doc/wiki/%E4%BD%9C%E6%88%90%E6%96%B9%E6%B3%95
  // Parse the sus file
  const data: ISusScore = SusAnalyzer.getScore(sus, 480)
  let result: Note[] = []

  // Calculate the starting milliseconds of each measure.
  let accumulator = 0
  const absMs: number[] = [0, ...data.BPMs.map((bpm, i) =>
    Math.floor(accumulator += (60 / bpm * 1000) * data.BEATs[i]))]

  function calcTime(note: ISusNotes) {
    // To calculate time: First add the absolute milliseconds of the measure,
    // then add the relative milliseconds of the tick within the measure.
    // To calculate the relative time:
    // - The number of ticks per beat is 480, so we do note.tick / 480 to get the number of beats.
    // - The number of beats per minute is data.BPMs[note.measure], so we do 60 / BPM to get the number of seconds per beat.
    // - Then, we multiply by 1000 to get the number of milliseconds per beat.
    // - Multiplied by the number of beats to get the number of milliseconds.
    return Math.floor(absMs[note.measure] + note.tick / 480 * 60 / data.BPMs[note.measure] * 1000)
  }

  const key = (note: Note | ISusNotes) => `${note.measure}_${note.tick}_${note.lane}`
  const attrs = (note: ISusNotes) => {
    return {
      t: calcTime(note),
      lane: note.lane, tick: note.tick, measure: note.measure, width: note.width,
    }
  }

  // use to remove overlapping tap + flick or tap + slide head
  let shortNotesMap: { [key: string]: Note } = Object.fromEntries(data.shortNotes.map((note: ISusNotes) => {
    let type = "unknown"
    if (note.lane == 0 && note.noteType == 4) {
      type = "skill"
    } else if (note.lane == 15 && note.noteType == 2) {
      type = "fever chance"
    } else if (note.lane == 15 && note.noteType == 1) {
      type = "fever"
    } else if (note.lane >= 2 && note.lane <= 13 && note.noteType == 1) {
      type = "tap"
    } else if (note.lane >= 2 && note.lane <= 13 && note.noteType == 2) {
      type = "yellow tap"
    } else if (note.lane >= 2 && note.lane <= 13 && note.noteType == 3) {
      type = "diamond" // combo point on slide, will not affect slide path
      // chunithm = flick note
      // When the flick notes of Chunithm are placed on the relay point or invisible relay point of the slide, the shape of the slide at the placed relay point is ignored and the relay points before and after are interpolated and connected.
      // In the case of an image, a relay point is placed on the refracting slide, and flick notes are placed on it.
      // Therefore, refraction is ignored and it is linear.
      // If flick notes are placed above an invisible relay point, the relay point will not be drawn.
    }

    return { type, r: "short", ...attrs(note) }
  }).map(note => [key(note), note]))

  // use to map airNote to slideNote
  let airNotesMap: { [key: string]: Note } = Object.fromEntries(data.airNotes.map(note => {
    let type = "unknown"
    if (note.noteType == 5) { // air down (left)
      type = "slide bend left"
    } else if (note.noteType == 6) { // air down (right)
      type = "slide bend right"
    } else if (note.noteType == 2) { // air down (middle)
      type = "slide bend middle"
    } else if (note.noteType == 1) { // air up (middle)
      type = "flick"
    } else if (note.noteType == 4) { // air up (right)
      type = "flick right"
    } else if (note.noteType == 3) { // air up (left)
      type = "flick left"
    }

    // Remove overlapping notes
    let shortNote: Note | undefined = shortNotesMap[key(note)]
    if (shortNote) delete shortNotesMap[key(note)]

    return { type, r: "air", ...attrs(note), shortNote }
  }).map(note => [key(note), note]))

  let slideId = 0
  let slides: Note[][] = []

  data.slideNotes.forEach(notes => {
    let type = "unknown"
    slides[slideId] = []
    for (let i = 0; i < notes.length; i++) {
      const note = notes[i];
      if (i == 0 && note.noteType == 1) {
        type = "slide head"
      } else if (i == notes.length - 1 && note.noteType == 2) {
        type = "slide tail"
      } else if (note.noteType == 3) {
        type = "slide waypoint hvcombo" // have diamond
      } else if (note.noteType == 5) {
        type = "slide waypoint nocombo"
      }

      // for merge overlaying airNotes to slide
      let airNote: Note | undefined = airNotesMap[key(note)]
      if (airNote) delete airNotesMap[key(note)]

      // check overlapping taps
      // expected taps type: yellow tap, diamond
      let shortNote: Note | undefined = shortNotesMap[key(note)]
      let diamondNote: Note | undefined = undefined;
      if (shortNote) {
        if (shortNote.type == "diamond") diamondNote = shortNote
        else delete shortNotesMap[key(note)]
      }

      let resultObject = { type, r: "slide", ...attrs(note),
        slideId, shortNote, airNote, diamondNote
      }
      slides[slideId].push(resultObject)
      result.push(resultObject)
    }
    slides[slideId].sort((a, b) => a.t - b.t)

    slideId += 1
  })

  // add remaining shortNotes to result
  for (const key in shortNotesMap) {
    if (!shortNotesMap.hasOwnProperty(key)) throw new Error("shortNotesMap hasOwnProperty error");
    result.push(shortNotesMap[key])
  }

  // add remaining airNotes to result
  // console.log("lonely airNotes", airNotesMap);
  for (const key in airNotesMap) {
    if (!airNotesMap.hasOwnProperty(key)) throw new Error("airNotesMap hasOwnProperty error");
    result.push(airNotesMap[key])
  }

  result = result.sort((a, b) => a.t - b.t)

  return { timestampNotes: result, slides }
}