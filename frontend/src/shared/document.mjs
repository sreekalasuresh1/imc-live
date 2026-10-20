export const EMPTY_DOC = { type: 'doc', content: [{ type: 'paragraph', content: [] }] };
export function createEmptyDocument(){ return structuredClone(EMPTY_DOC); }
export function createDocument(){ return createEmptyDocument(); }
export function serializeDocument(doc){ try{ return JSON.stringify(doc);}catch{return '{}';}}
export function deserializeDocument(str){ try{ return JSON.parse(str);}catch{ return createEmptyDocument();}}
export function isEmptyDoc(doc){ return !doc || !doc.content || doc.content.length===0; }
export function applyCommand(doc, cmd){ return doc; }
export function validateDocument(doc){ return true; }
export const document = EMPTY_DOC;
export default EMPTY_DOC;
