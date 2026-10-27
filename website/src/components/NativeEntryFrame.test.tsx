import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { WorkspaceEntry } from '@/api/workspace'
import { BRIDGE_CHANNEL } from '@/lib/nativeBridge'
import { LegacyEntryFrame, NativeEntryFrame } from './NativeEntryFrame'

function entry(overrides: Partial<WorkspaceEntry> = {}): WorkspaceEntry {
  return {
    key: 'src:entry',
    sourceId: 'src_fixture',
    revision: 'rev_fixture_0001',
    sourceTitle: 'Fixture source',
    headword: 'right',
    recordOrdinal: 0,
    html: '<style>body{color:#123}.entry{display:grid}</style><p class="entry">Correct.</p>',
    textBlocks: [],
    renderTrust: 'safe-v2',
    ...overrides,
  }
}

function capabilityFrom(frame: HTMLIFrameElement): string {
  const match = frame.srcdoc.match(/const capability = "([a-f0-9]{32})"/)
  if (!match) throw new Error('capability not found')
  return match[1]
}

function bridgeEvent(frame: HTMLIFrameElement, data: unknown): MessageEvent {
  return new MessageEvent('message', {
    data,
    origin: 'null',
    source: frame.contentWindow,
  })
}

describe('NativeEntryFrame', () => {
  it('uses an opaque sandbox with no navigation, popup, form, download, or same-origin grants', () => {
    render(<NativeEntryFrame entry={entry()} onEntry={() => {}} />)
    const frame = screen.getByTitle('Fixture source: right') as HTMLIFrameElement

    expect(frame.getAttribute('sandbox')).toBe('allow-scripts')
    expect(frame.getAttribute('sandbox')).not.toContain('allow-same-origin')
    expect(frame.getAttribute('sandbox')).not.toContain('allow-popups')
    expect(frame.srcdoc).toContain('.entry{display:grid}')
  })

  it('keeps conflicting global selectors isolated in separate documents', () => {
    render(
      <>
        <NativeEntryFrame entry={entry({ key: 'one', html: '<style>body{color:red}.entry{display:block}</style><p>One</p>' })} onEntry={() => {}} />
        <NativeEntryFrame entry={entry({ key: 'two', sourceTitle: 'Second source', html: '<style>body{color:blue}.entry{display:grid}</style><p>Two</p>' })} onEntry={() => {}} />
      </>,
    )
    const first = screen.getByTitle('Fixture source: right') as HTMLIFrameElement
    const second = screen.getByTitle('Second source: right') as HTMLIFrameElement

    expect(first.srcdoc).toContain('body{color:red}')
    expect(first.srcdoc).not.toContain('body{color:blue}')
    expect(second.srcdoc).toContain('body{color:blue}')
    expect(second.srcdoc).not.toContain('body{color:red}')
  })

  it('accepts entry and height only from the expected frame and render capability', () => {
    const onEntry = vi.fn()
    render(<NativeEntryFrame entry={entry()} onEntry={onEntry} />)
    const frame = screen.getByTitle('Fixture source: right') as HTMLIFrameElement
    const capability = capabilityFrom(frame)

    act(() => {
      window.dispatchEvent(
        bridgeEvent(frame, {
          channel: BRIDGE_CHANNEL,
          capability: 'f'.repeat(32),
          type: 'entry',
          payload: { word: 'forged' },
        }),
      )
      window.dispatchEvent(
        bridgeEvent(frame, {
          channel: BRIDGE_CHANNEL,
          capability,
          type: 'entry',
          payload: { word: 'correct' },
        }),
      )
      window.dispatchEvent(
        bridgeEvent(frame, {
          channel: BRIDGE_CHANNEL,
          capability,
          type: 'ready',
          payload: {},
        }),
      )
      window.dispatchEvent(
        bridgeEvent(frame, {
          channel: BRIDGE_CHANNEL,
          capability,
          type: 'height',
          payload: { height: 640 },
        }),
      )
    })

    expect(onEntry).toHaveBeenCalledTimes(1)
    expect(onEntry).toHaveBeenCalledWith('correct')
    expect(frame.style.height).toBe('640px')
  })

  it('keeps legacy source scripts inert by granting no sandbox capability', () => {
    render(
      <LegacyEntryFrame
        entry={entry({
          renderTrust: 'legacy-inert',
          html: '<script>window.legacyRan=true</script><p>Readable.</p>',
        })}
      />,
    )
    const frame = screen.getByTitle('Fixture source: legacy inert rendering') as HTMLIFrameElement

    expect(frame.getAttribute('sandbox')).toBe('')
    expect(frame.srcdoc).toContain('window.legacyRan=true')
    expect(screen.getByText(/Legacy fallback/)).toBeInTheDocument()
  })

  it('offers a safe full-source dialog after bridge degradation', () => {
    vi.useFakeTimers()
    render(<NativeEntryFrame entry={entry()} onEntry={() => {}} />)

    act(() => vi.advanceTimersByTime(1_600))
    fireEvent.click(screen.getByRole('button', { name: /Full source view/ }))
    act(() => vi.runOnlyPendingTimers())

    expect(screen.getByRole('dialog', { name: /full source/i })).toHaveAttribute('open')
    expect(screen.getByRole('button', { name: /Return to results/ })).toHaveFocus()
    vi.useRealTimers()
  })
})
