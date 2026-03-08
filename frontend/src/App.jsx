import React, { useState, useEffect } from 'react'
import './App.css'

const API_BASE = "http://localhost:8000"

function App() {
  const [step, setStep] = useState(1)
  const [docId, setDocId] = useState(null)
  const [filename, setFilename] = useState("")
  const [profile, setProfile] = useState(null)
  const [extraction, setExtraction] = useState(null)
  const [pageIndex, setPageIndex] = useState(null)
  const [query, setQuery] = useState("")
  const [answer, setAnswer] = useState("")
  const [loading, setLoading] = useState(false)
  const [availableFiles, setAvailableFiles] = useState([])

  useEffect(() => {
    fetch(`${API_BASE}/files`)
      .then(res => res.json())
      .then(data => setAvailableFiles(data.files || []))
      .catch(err => console.error("Error fetching files:", err))
  }, [])

  const handleSelectFile = (file) => {
    setDocId(file)
    setFilename(file)
    setStep(1)
    setProfile(null)
    setExtraction(null)
    setPageIndex(null)
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData })
      const data = await res.json()
      setDocId(data.doc_id)
      setFilename(data.filename)
      setStep(1)
    } finally {
      setLoading(false)
    }
  }

  const runTriage = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/triage/${docId}`)
      const data = await res.json()
      setProfile(data)
    } finally {
      setLoading(false)
    }
  }

  const runExtraction = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/extract/${docId}`)
      const data = await res.json()
      setExtraction(data)
    } finally {
      setLoading(false)
    }
  }

  const loadPageIndex = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/pageindex/${docId}`)
      const data = await res.json()
      setPageIndex(data)
    } catch (e) {
      alert("PageIndex not found. Please ensure extraction and indexing are complete.")
    } finally {
      setLoading(false)
    }
  }

  const askQuery = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, query })
      })
      const data = await res.json()
      setAnswer(data.answer)
    } finally {
      setLoading(false)
    }
  }

  const renderStep1 = () => (
    <div className="step-container">
      <h2>Step 1: The Triage</h2>
      <p>Analyze document characteristics and select extraction strategy.</p>

      {!docId ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-card" style={{ textAlign: 'center', cursor: 'pointer' }} onClick={() => document.getElementById('file-input').click()}>
            <input id="file-input" type="file" hidden onChange={handleUpload} />
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📁</div>
            <h3>Drop a document into the pipeline</h3>
            <p>Support for native & scanned PDFs</p>
          </div>

          <div className="glass-card">
            <h3>Or select from Data Corpus</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
              {availableFiles.map(file => (
                <div
                  key={file}
                  className="viewer-panel"
                  style={{ cursor: 'pointer', padding: '10px', fontSize: '0.9rem', border: '1px solid rgba(255,255,255,0.1)' }}
                  onClick={() => handleSelectFile(file)}
                >
                  📄 {file}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0 }}>{filename}</h3>
              <p style={{ color: '#4ecca3', fontSize: '0.9rem' }}>ID: {docId}</p>
            </div>
            {!profile && <button className="premium-button" onClick={runTriage} disabled={loading}>{loading ? 'Analyzing...' : 'Run Triage'}</button>}
          </div>
          {profile && (
            <div style={{ marginTop: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <ProfileItem label="Origin" value={profile.overall_origin_type} />
              <ProfileItem label="Complexity" value={profile.overall_layout_complexity} />
              <ProfileItem label="Language" value={`${profile.language?.code || 'Unknown'} (${Math.round((profile.language?.confidence || 0) * 100)}%)`} />
              <ProfileItem label="Strategy" value={profile.overall_estimated_cost || 'fast_text_sufficient'} highlight />
              <ProfileItem label="Domain" value={profile.domain_hint || 'general'} />
            </div>
          )}
        </div>
      )}
    </div>
  )

  const renderStep2 = () => (
    <div className="step-container">
      <h2>Step 2: The Extraction</h2>
      <p>High-fidelity extraction with confidence-gated escalation.</p>
      {!extraction ? (
        <button className="premium-button" onClick={runExtraction} disabled={loading}>{loading ? 'Extracting...' : 'Start Extraction'}</button>
      ) : (
        <div className="side-by-side">
          <div className="viewer-panel">
            <h4>Raw Document Content</h4>
            {extraction.map(page => (
              <div key={page.page} style={{ marginBottom: '1.5rem', background: 'rgba(255,255,255,0.05)', padding: '10px', borderRadius: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', opacity: 0.6 }}>
                  <span>Page {page.page}</span>
                  <span style={{ color: (page.confidence || 0) < 0.6 ? '#f87171' : '#4ecca3' }}>
                    Strategy: {page.strategy_used || 'fast_text'} | Confidence: {Math.round((page.confidence || 0) * 100)}%
                  </span>
                </div>
                {page.error ? (
                  <p style={{ color: '#f87171', fontSize: '0.8rem', margin: '6px 0 0' }}>⚠ {page.error}</p>
                ) : (
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', margin: '6px 0 0' }}>
                    {page.content?.text_blocks?.length
                      ? page.content.text_blocks.map(b => b.text).join('\n').substring(0, 600)
                      : '(No text extracted — document may be scanned or image-only)'}
                  </pre>
                )}
              </div>
            ))}
          </div>
          <div className="viewer-panel">
            {/* <h4>Structured Data (JSON)</h4> */}
            {/* <div className="glass-card" style={{ padding: '1rem', background: '#1a1a2e' }}>
              <pre style={{ fontSize: '0.8rem', color: '#4ecca3' }}>
                {JSON.stringify(extraction[0]?.content?.tables || [], null, 2)}
              </pre>
            </div> */}
            <div style={{ marginTop: '1rem' }}>
              <h4>Extraction Ledger</h4>
              <div className="glass-card" style={{ padding: '0.8rem', fontSize: '0.8rem', background: 'rgba(0,0,0,0.3)', overflowX: 'auto' }}>
                <pre style={{ margin: 0 }}>{JSON.stringify({
                  doc_id: docId,
                  strategy_used: extraction[0]?.strategy_used,
                  confidence: extraction[0]?.confidence,
                  pages_extracted: extraction.length,
                  errors: extraction.filter(p => p.error).length
                }, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  const renderStep3 = () => (
    <div className="step-container">
      <h2>Step 3: The PageIndex</h2>
      <p>Navigate a document-aware hierarchical navigation tree.</p>
      {!pageIndex ? (
        <button className="premium-button" onClick={loadPageIndex} disabled={loading}>{loading ? 'Loading Tree...' : 'Generate PageIndex'}</button>
      ) : (
        <div className="glass-card">
          <h3>PageIndex for {filename}</h3>
          <div className="tree-node">
            <TreeNode node={pageIndex.root} />
          </div>
        </div>
      )}
    </div>
  )

  const renderStep4 = () => (
    <div className="step-container">
      <h2>Step 4: Query with Provenance</h2>
      <p>Natural language Q&A with spatial citations and audit-ready proof.</p>
      <div className="glass-card">
        <div style={{ display: 'flex', gap: '1rem' }}>
          <input
            type="text"
            className="viewer-panel"
            style={{ flex: 1, border: '1px solid rgba(255,255,255,0.2)' }}
            placeholder="Ask a question about the document..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="premium-button" onClick={askQuery} disabled={loading}>{loading ? 'Thinking...' : 'Query'}</button>
        </div>
        {answer && (
          <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '12px' }}>
            <p style={{ margin: 0, fontSize: '1.1rem', lineHeight: '1.6' }}>
              {renderAnswerWithCitations(answer)}
            </p>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div className="App">
      <header>
        <p style={{ color: '#4ecca3', fontWeight: 600, letterSpacing: '2px', margin: 0 }}>FDE PROGRAM</p>
        <h1>Refinery Interface</h1>
        <p style={{ opacity: 0.6 }}>Enterprise-scale Document Understanding Pipeline</p>
      </header>

      <div className="stepper">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className={`step-node ${step >= i ? 'active' : ''}`} onClick={() => setStep(i)} style={{ cursor: 'pointer' }}>
            {i}
          </div>
        ))}
      </div>

      <main>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        {step === 4 && renderStep4()}
      </main>

      {step < 4 && docId && (
        <button
          className="premium-button"
          style={{ marginTop: '2rem', background: 'transparent', border: '1px solid #4ecca3', color: '#4ecca3' }}
          onClick={() => setStep(step + 1)}
        >
          Continue to Step {step + 1} →
        </button>
      )}
    </div>
  )
}

const ProfileItem = ({ label, value, highlight }) => (
  <div style={{ background: 'rgba(255,255,255,0.05)', padding: '10px 15px', borderRadius: '12px' }}>
    <span style={{ fontSize: '0.75rem', opacity: 0.6, display: 'block', textTransform: 'uppercase' }}>{label}</span>
    <span style={{ fontWeight: 600, color: highlight ? '#4ecca3' : 'white' }}>{value}</span>
  </div>
)

const TreeNode = ({ node }) => {
  const [open, setOpen] = useState(true)
  return (
    <div style={{ marginTop: '8px' }}>
      <div onClick={() => setOpen(!open)} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
        <span style={{ marginRight: '8px' }}>{node.child_sections?.length ? (open ? '▼' : '▶') : '•'}</span>
        <span style={{ fontWeight: 500 }}>{node.title}</span>
        <span style={{ marginLeft: '10px', fontSize: '0.8rem', opacity: 0.5 }}>pp. {node.page_start}-{node.page_end}</span>
      </div>
      {open && node.child_sections && (
        <div className="tree-node">
          {node.child_sections.map((child, i) => <TreeNode key={i} node={child} />)}
        </div>
      )}
    </div>
  )
}

const renderAnswerWithCitations = (text) => {
  // Simple regex to find [Doc: ..., Page: ...]
  const parts = text.split(/(\[Doc:.*?, Page:.*?\])/g)
  return parts.map((part, i) => {
    if (part.startsWith('[Doc:')) {
      return <span key={i} className="citation" title="Verified Source">{part}</span>
    }
    return part
  })
}

export default App
