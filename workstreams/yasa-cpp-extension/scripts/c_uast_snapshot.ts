/**
 * Fingerprint the UAST that a built parser-C produces for every .c/.h file of a corpus.
 *
 * Used to prove that changes to parser-C leave C output byte-identical.
 * Each file is parsed on its own with the Linux target (no include resolution);
 * `sourcefile` is the path relative to the corpus root, so absolute paths never
 * enter the hash.
 *
 * Usage: tsx c_uast_snapshot.ts <parser-C dir> <corpus root> <out.json>
 */
import * as crypto from 'crypto'
import * as fs from 'fs'
import * as path from 'path'

/**
 * @param root - directory to walk (symlinked directories are followed)
 * @returns paths of .c and .h files, relative to root, sorted
 */
function sourceFiles(root: string): string[] {
  const out: string[] = []
  const walk = (dir: string) => {
    for (const name of fs.readdirSync(dir)) {
      if (name === '.git' || name === 'node_modules') continue
      const full = path.join(dir, name)
      const stat = fs.statSync(full)
      if (stat.isDirectory()) walk(full)
      else if (/\.[ch]$/.test(name)) out.push(path.relative(root, full))
    }
  }
  walk(root)
  return out.sort()
}

/**
 * @param value - parsed UAST
 * @returns sha256 of its JSON without parent links
 */
function fingerprint(value: unknown): string {
  const json = JSON.stringify(value, (key, v) => (key === 'parent' ? undefined : v))
  return crypto.createHash('sha256').update(json).digest('hex')
}

async function main(): Promise<void> {
  const [parserDir, corpusRoot, outFile] = process.argv.slice(2)
  if (!parserDir || !corpusRoot || !outFile) {
    console.error('usage: c_uast_snapshot.ts <parser-C dir> <corpus root> <out.json>')
    process.exit(2)
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Parser } = require(path.resolve(parserDir, 'dist/src/index.js'))
  const parser = new Parser()
  await parser.init()
  const result: Record<string, string> = {}
  for (const rel of sourceFiles(corpusRoot)) {
    const content = fs.readFileSync(path.join(corpusRoot, rel), 'utf8')
    try {
      result[rel] = fingerprint(parser.parse(content, { sourcefile: rel, preprocessor: { target: 'linux' } }))
    } catch (error) {
      result[rel] = `ERROR: ${String((error as Error)?.message ?? error).slice(0, 200)}`
    }
  }
  fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true })
  fs.writeFileSync(outFile, JSON.stringify(result, null, 1) + '\n')
  const errors = Object.values(result).filter((v) => v.startsWith('ERROR')).length
  console.log(`${Object.keys(result).length} files, ${errors} parse exceptions -> ${outFile}`)
}

main()
