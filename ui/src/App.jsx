import { useState } from 'react'

const API_URL = 'http://127.0.0.1:8000/api'

function App() {
  const [folderPath, setFolderPath] = useState('/Volumes/RANDY-M2B/MUSIC/2024/')
  const [files, setFiles] = useState([])
  const [results, setResults] = useState({})
  const [isScanning, setIsScanning] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analyzingIndex, setAnalyzingIndex] = useState(-1)
  const [isMoving, setIsMoving] = useState(false)
  const [moveStats, setMoveStats] = useState(null)
  const [isSelecting, setIsSelecting] = useState(false)
  const [expandedItems, setExpandedItems] = useState({})

  const toggleExpand = (path) => {
    setExpandedItems(prev => ({ ...prev, [path]: !prev[path] }))
  }

  const handleSelectFolder = async () => {
    setIsSelecting(true)
    try {
      const res = await fetch(`${API_URL}/select_folder`)
      const data = await res.json()
      if (data.status === 'success' && data.path) {
        setFolderPath(data.path)
        await loadFolderData(data.path)
      } else if (data.status === 'error') {
        alert("Error al abrir selector de carpetas: " + data.message)
      }
    } catch (e) {
      alert("Error contactando al servidor")
    } finally {
      setIsSelecting(false)
    }
  }

  const loadFolderData = async (pathString) => {
    if (!pathString) return
    setIsScanning(true)
    setFiles([])
    setResults({})
    setMoveStats(null)
    setAnalyzingIndex(-1)
    
    try {
      const res = await fetch(`${API_URL}/scan_folder?path=${encodeURIComponent(pathString)}`)
      if (!res.ok) throw new Error('Carpeta no encontrada o inválida')
      const data = await res.json()
      
      setFiles(data.files)
    } catch (e) {
      alert(e.message)
    } finally {
      setIsScanning(false)
    }
  }

  const handleLoadFolder = () => {
    loadFolderData(folderPath)
  }

  const handleAnalyze = async () => {
    if (files.length === 0) return
    setIsAnalyzing(true)
    setMoveStats(null)
    
    // Comenzar análisis uno por uno
    for (let i = 0; i < files.length; i++) {
      setAnalyzingIndex(i)
      const file = files[i]
      
      // Si ya tiene resultado, saltarlo (por si se pauso/continue)
      if (results[file.fullpath]) continue
      
      try {
        const aRes = await fetch(`${API_URL}/analyze_file?filepath=${encodeURIComponent(file.fullpath)}`)
        const aData = await aRes.json()
        setResults(prev => ({ ...prev, [file.fullpath]: aData }))
      } catch (e) {
        setResults(prev => ({ ...prev, [file.fullpath]: { status: 'error' } }))
      }
    }
    setIsAnalyzing(false)
    setAnalyzingIndex(-1)
  }

  const handleMoveFakes = async () => {
    const fakesToMove = files
      .map(f => f.fullpath)
      .filter(path => results[path]?.detected_status === 'Fake')
      
    if (fakesToMove.length === 0) return alert("No hay archivos Fake para mover")
    
    setIsMoving(true)
    try {
      const res = await fetch(`${API_URL}/move_fakes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: fakesToMove, folder_path: folderPath })
      })
      const data = await res.json()
      setMoveStats(data)
    } catch (e) {
      alert("Error moviendo archivos")
    } finally {
      setIsMoving(false)
    }
  }

  const fakesCount = files.filter(f => results[f.fullpath]?.detected_status === 'Fake').length
  const isFinished = files.length > 0 && analyzingIndex === -1 && !isAnalyzing && Object.keys(results).length === files.length
  
  const isUIBusy = isScanning || isAnalyzing || isMoving || isSelecting

  return (
    <div>
      <h1>RANDY <span style={{fontWeight: 300}}>VISUALIZER AUDIO</span></h1>
      <p className="subtitle">Detector de espectrogramas y Fakes por Inteligencia de Frecuencias</p>

      <div className="glass-panel">
        <label style={{display: 'block', marginBottom: '0.5rem', fontWeight: 600}}>Directorio a Analizar:</label>
        <div className="input-group">
          <input 
            type="text" 
            value={folderPath} 
            onChange={e => setFolderPath(e.target.value)}
            disabled={isUIBusy}
            placeholder="/Ruta/a/tu/carpeta"
          />
          <button className="btn-secondary" onClick={handleSelectFolder} disabled={isUIBusy}>
             {isSelecting ? 'Abriendo...' : 'Examinar...'}
          </button>
          {files.length === 0 && (
            <button onClick={handleLoadFolder} disabled={isUIBusy}>
               {isScanning ? <span className="spinner"></span> : 'Cargar'}
            </button>
          )}
        </div>
        
        {files.length > 0 && !isAnalyzing && Object.keys(results).length === 0 && (
           <div style={{padding: '1.5rem', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid var(--accent)', borderRadius: 8, marginBottom: '2rem', textAlign: 'center'}}>
              <h2 style={{marginTop: 0, color: 'white'}}>¡Carpeta Cargada!</h2>
              <p>Se econtraron <strong>{files.length}</strong> archivos de audio listos para ser analizados de forma segura.</p>
              <button style={{marginTop: '0.5rem', fontSize: '1.1rem'}} onClick={handleAnalyze}>
                 ▶ Iniciar Análisis de los {files.length} archivos
              </button>
           </div>
        )}
        
        {isAnalyzing && files.length > 0 && (
          <div className="progress-container">
            <div className="progress-text" style={{display: 'flex', justifyContent: 'space-between'}}>
               <span>Analizando archivo {analyzingIndex + 1} de {files.length}...</span>
               <span style={{fontWeight: 'bold'}}>{Math.round(((analyzingIndex)/files.length)*100)}%</span>
            </div>
            <div style={{height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 3, overflow: 'hidden'}}>
               <div style={{
                 height: '100%', 
                 background: 'var(--accent)', 
                 width: `${((analyzingIndex)/files.length)*100}%`,
                 transition: 'width 0.2s linear'
               }}></div>
            </div>
          </div>
        )}
        
        {moveStats && (
            <div style={{padding: '1rem', background: 'rgba(63, 185, 80, 0.1)', border: '1px solid var(--success)', borderRadius: 8, marginBottom: '1rem'}}>
               <strong style={{color: 'var(--success)'}}>¡Operación Exitosa!</strong><br/>
               Se movieron {moveStats.moved} archivos fakes a: <br/> <code>{moveStats.fake_folder}</code>
            </div>
        )}

      </div>

      <div className="results-list">
        {files.map((file, i) => {
          const res = results[file.fullpath]
          const isCurrent = analyzingIndex === i
          const isExpanded = !!expandedItems[file.fullpath]
          
          return (
            <div key={file.fullpath} className="glass-panel card" style={{ borderColor: isCurrent ? 'var(--accent)' : '' }}>
              <div className="card-header">
                <div className="header-left">
                  <div className="filename">{file.name}</div>
                  {!res && isCurrent && <span className="badge pending"><span className="spinner" style={{width: 12, height:12, borderWidth: 2}}></span></span>}
                  {!res && !isCurrent && <span className="badge pending">Esperando</span>}
                  {res && res.status === 'success' && (
                    <span className={`badge ${res.detected_status === 'Fake' ? 'fake' : 'sana'}`}>
                      {res.detected_status}
                    </span>
                  )}
                </div>
                
                <div className="header-right">
                   {res && res.status === 'success' && (
                     <button className="btn-secondary btn-small" onClick={() => toggleExpand(file.fullpath)}>
                         {isExpanded ? 'Ocultar Detalle' : 'Ver Imagen y Detalle'}
                     </button>
                   )}
                </div>
              </div>
              
              {isExpanded && res && res.status === 'success' && (
                 <div className="details-panel">
                    <div className="quality-info">{res.quality}</div>
                    <div className="explanation">
                       <strong>Diagnóstico: </strong> {res.explanation}
                    </div>
                    {res.spectrogram ? (
                       <img src={res.spectrogram} className="spectrogram" alt="Spectrogram" />
                    ) : (
                       <div className="spectrogram" style={{opacity: 0.1, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                          Sin datos de imagen
                       </div>
                    )}
                 </div>
              )}
            </div>
          )
        })}
      </div>

      {isFinished && fakesCount > 0 && !moveStats && (
        <button className="btn-danger" onClick={handleMoveFakes} disabled={isMoving}>
           {isMoving ? 'MOVIENDO...' : `Mover los ${fakesCount} archivos Fake a la carpeta FAKE-AUDIO`}
        </button>
      )}

    </div>
  )
}

export default App
