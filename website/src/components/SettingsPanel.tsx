import { useEffect, useRef, useState } from 'react'
import { KeyRound, Moon, Sun, X } from 'lucide-react'
import { getV2Token, setV2Token, type WorkspaceSource } from '@/api/workspace'
import { useRefreshWorkspace, useUpdateWorkspaceSource } from '@/hooks/useWorkspace'
import { useAppStore } from '@/stores/useAppStore'

interface SettingsPanelProps {
  sources: WorkspaceSource[]
  returnFocusRef: React.RefObject<HTMLButtonElement | null>
}

export function SettingsPanel({ sources, returnFocusRef }: SettingsPanelProps) {
  const open = useAppStore((state) => state.settingsOpen)
  const setOpen = useAppStore((state) => state.setSettingsOpen)
  const darkMode = useAppStore((state) => state.darkMode)
  const toggleDarkMode = useAppStore((state) => state.toggleDarkMode)
  const [token, setToken] = useState(getV2Token())
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const updateSource = useUpdateWorkspaceSource()
  const refreshWorkspace = useRefreshWorkspace()

  useEffect(() => {
    if (open) {
      setToken(getV2Token())
      dialogRef.current?.showModal()
      closeButtonRef.current?.focus()
    }
  }, [open])

  if (!open) return null
  const close = () => {
    setOpen(false)
    window.setTimeout(() => returnFocusRef.current?.focus(), 0)
  }
  const saveToken = () => {
    setV2Token(token)
    refreshWorkspace()
  }

  return (
      <dialog
        ref={dialogRef}
        className="settings-drawer"
        aria-label="Workspace settings"
        onCancel={(event) => { event.preventDefault(); close() }}
        onClose={close}
      >
        <header>
          <div><span className="eyebrow">Workspace</span><h2>Settings</h2></div>
          <button ref={closeButtonRef} className="icon-button" aria-label="Close settings" onClick={close}><X size={18} /></button>
        </header>
        <section className="settings-section">
          <h3>Appearance</h3>
          <button className="setting-row" onClick={toggleDarkMode}>
            <span>{darkMode ? <Moon size={17} /> : <Sun size={17} />} Dark workspace</span>
            <span className={`switch ${darkMode ? 'is-on' : ''}`} aria-hidden="true"><i /></span>
          </button>
          <p>Native dictionary documents keep their own source colors.</p>
        </section>
        <section className="settings-section">
          <h3>Private v2 connection</h3>
          <label className="token-field">
            <span><KeyRound size={15} /> Session token</span>
            <input type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" />
          </label>
          <div className="button-row">
            <button className="primary-button" onClick={saveToken}>Use v2</button>
            <button className="secondary-button" onClick={() => { setToken(''); setV2Token(''); refreshWorkspace() }}>Use legacy fallback</button>
          </div>
          <p>The token stays in this browser tab’s session storage and is never forwarded into dictionary frames.</p>
        </section>
        <section className="settings-section">
          <h3>Sources</h3>
          <div className="settings-source-list">
            {sources.map((source) => (
              <button
                key={source.id}
                className="setting-row"
                onClick={() => updateSource.mutate({ sourceId: source.id, enabled: !source.enabled })}
              >
                <span><span className="source-glyph small">{source.title.slice(0, 1)}</span>{source.title}</span>
                <span className={`switch ${source.enabled ? 'is-on' : ''}`} aria-hidden="true"><i /></span>
              </button>
            ))}
          </div>
        </section>
      </dialog>
  )
}
