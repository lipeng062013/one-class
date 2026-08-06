import client from './client'

export interface IntegrationsStatus {
  llm: {
    configured: boolean
    model: string | null
    base_url_set: boolean
  }
  image: {
    configured: boolean
    model: string | null
    base_url_set: boolean
  }
  notes: Record<string, string>
}

/** @param opts.silent 失败时不弹全局 toast（如学管师无 system.read 时工作台静默跳过） */
export async function getIntegrationsStatus(opts?: {
  silent?: boolean
}): Promise<IntegrationsStatus> {
  const res = await client.get('/system/integrations', {
    skipErrorToast: opts?.silent === true,
  } as Parameters<typeof client.get>[1])
  return res.data.data
}
