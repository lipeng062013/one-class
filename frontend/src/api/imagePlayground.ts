import client from './client'

export interface ImagePlaygroundConfig {
  ready: boolean
  model: string
  /** Same-origin proxy path; real IMAGE_API_BASE_URL stays on server */
  api_base_path: string
  notes?: Record<string, string>
}

interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

const PLAYGROUND_STORAGE_KEY = 'gpt-image-playground'
const DEFAULT_PROFILE_ID = 'default-openai'

export async function getImagePlaygroundConfig(): Promise<ImagePlaygroundConfig> {
  const res = await client.get<ApiResponse<ImagePlaygroundConfig>>('/image-playground/config')
  if (!res.data.data) {
    throw new Error(res.data.error?.message || 'Failed to load image playground config')
  }
  return res.data.data
}

/** Absolute same-origin proxy base for the playground (no upstream URL in browser). */
export function resolveProxyApiUrl(apiBasePath: string): string {
  if (apiBasePath.startsWith('http://') || apiBasePath.startsWith('https://')) {
    return apiBasePath.replace(/\/+$/, '')
  }
  const path = apiBasePath.startsWith('/') ? apiBasePath : `/${apiBasePath}`
  return `${window.location.origin}${path}`.replace(/\/+$/, '')
}

/**
 * Write proxy API URL + login JWT onto playground「默认」profile.
 * Upstream IMAGE_* is applied only on the server by the proxy.
 */
export function applyProxyApiToDefaultProfile(opts: {
  apiUrl: string
  apiKey: string
  model?: string
}): void {
  let version = 2
  let state: Record<string, unknown> = {}

  try {
    const raw = localStorage.getItem(PLAYGROUND_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as { state?: Record<string, unknown>; version?: number }
      if (parsed?.state && typeof parsed.state === 'object') state = { ...parsed.state }
      if (typeof parsed?.version === 'number') version = parsed.version
    }
  } catch {
    state = {}
  }

  const prevSettings =
    state.settings && typeof state.settings === 'object' && !Array.isArray(state.settings)
      ? ({ ...(state.settings as Record<string, unknown>) } as Record<string, unknown>)
      : {}

  const prevProfiles = Array.isArray(prevSettings.profiles) ? [...prevSettings.profiles] : []
  const profiles = prevProfiles.map((item) =>
    item && typeof item === 'object' ? { ...(item as Record<string, unknown>) } : item,
  )

  const defaultIndex = profiles.findIndex(
    (item) =>
      item &&
      typeof item === 'object' &&
      ((item as Record<string, unknown>).id === DEFAULT_PROFILE_ID ||
        (item as Record<string, unknown>).name === '默认'),
  )

  const model = (opts.model || '').trim() || 'gpt-image-2'

  if (defaultIndex >= 0) {
    const current = profiles[defaultIndex] as Record<string, unknown>
    profiles[defaultIndex] = {
      ...current,
      id: typeof current.id === 'string' ? current.id : DEFAULT_PROFILE_ID,
      name: '默认',
      provider: 'openai',
      baseUrl: opts.apiUrl,
      apiKey: opts.apiKey,
      model,
    }
  } else {
    profiles.unshift({
      id: DEFAULT_PROFILE_ID,
      name: '默认',
      provider: 'openai',
      baseUrl: opts.apiUrl,
      apiKey: opts.apiKey,
      model,
      timeout: 600,
      apiMode: 'images',
      codexCli: false,
      apiProxy: false,
      streamImages: false,
      streamPartialImages: 0,
    })
  }

  const activeId =
    defaultIndex >= 0
      ? String((profiles[defaultIndex] as Record<string, unknown>).id || DEFAULT_PROFILE_ID)
      : DEFAULT_PROFILE_ID

  state.settings = {
    ...prevSettings,
    profiles,
    activeProfileId: activeId,
    baseUrl: opts.apiUrl,
    apiKey: opts.apiKey,
    model,
  }

  if (!state.params || typeof state.params !== 'object') {
    state.params = {
      size: 'auto',
      quality: 'auto',
      output_format: 'png',
      output_compression: null,
      moderation: 'auto',
      n: 1,
      transparent_output: false,
    }
  }
  if (state.appMode == null) state.appMode = 'gallery'
  if (!Array.isArray(state.dismissedCodexCliPrompts)) state.dismissedCodexCliPrompts = []
  if (state.galleryInputDraft === undefined) state.galleryInputDraft = null
  if (state.activeAgentConversationId === undefined) state.activeAgentConversationId = null
  if (!state.agentInputDrafts || typeof state.agentInputDrafts !== 'object') state.agentInputDrafts = {}
  if (state.agentSidebarCollapsed == null) state.agentSidebarCollapsed = false
  if (state.agentAssetTab == null) state.agentAssetTab = 'references'
  if (state.agentAssetPanelCollapsed == null) state.agentAssetPanelCollapsed = false
  if (!Array.isArray(state.favoriteCollections)) state.favoriteCollections = []
  if (state.defaultFavoriteCollectionId === undefined) state.defaultFavoriteCollectionId = null
  if (state.supportPromptDismissed == null) state.supportPromptDismissed = false
  if (state.supportPromptOpen == null) state.supportPromptOpen = false
  if (state.supportPromptSkippedForImportedData == null) state.supportPromptSkippedForImportedData = false

  localStorage.setItem(PLAYGROUND_STORAGE_KEY, JSON.stringify({ state, version }))
}

export function buildPlaygroundIframeSrc(opts: {
  apiUrl: string
  apiKey: string
  model: string
}): string {
  const params = new URLSearchParams({
    apiUrl: opts.apiUrl,
    apiKey: opts.apiKey,
    model: opts.model || 'gpt-image-2',
    apiMode: 'images',
    profileName: '默认',
  })
  return `/gpt-image-playground/index.html?${params.toString()}`
}
