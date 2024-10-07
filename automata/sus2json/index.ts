import { readFileSync, writeFileSync, readdirSync, existsSync } from 'fs'
import { join } from 'path'
import { read } from './sekai-sus-reader'

const base_dir = 'X:\\rhythm-game\\Sekai\\music\\music_score'

// Function to process each difficulty file
async function processFile(dir: string, file: string) {
  let difficulty = file.split('.')[0]
  const ouf = join(dir, `${difficulty}.json`)
  // Check if the file already exists
  if (existsSync(ouf)) {
    console.log(`File ${ouf} already exists, skipping...`)
    return
  }
  writeFileSync(ouf, JSON.stringify(read(readFileSync(join(dir, file), 'utf8')), null, 2))
  console.log(`Processed ${dir}/${file}`)
}

// Main processing function
const processDirectory = async () => {
  console.log('Listing directories...')
  const directories = readdirSync(base_dir)
  let processedCount = 0
  console.log(`Found ${directories.length} directories`)

  // Use Promise.all to handle multiple directories in parallel
  await Promise.all(
    directories.map(async (raw_id) => {
      let dir = join(base_dir, raw_id)
      const files = readdirSync(dir)

      await Promise.all(files.map(async (file) => {
        await processFile(dir, file)
        processedCount++
        // Simple progress report
        console.log(`Processed ${processedCount} out of ${directories.length * files.length} files`)
      }))
    })
  )
  console.log('Processing completed!')
}

// Execute the main function
processDirectory().catch(console.error)

