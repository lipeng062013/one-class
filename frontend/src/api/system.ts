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

export async function getIntegrationsStatus(): Promise<IntegrationsStatus> {
  const res = await client.get('/system/integrations')
  return res.data.data
}
