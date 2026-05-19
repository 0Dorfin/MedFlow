function wrapFetchError(err: unknown, timeoutMs: number): Error {
  if (err instanceof Error && err.name === "AbortError") {
    return new Error(
      `Tiempo de espera agotado (${Math.round(timeoutMs / 1000)}s). El audio puede ser demasiado largo o el servicio esta ocupado.`,
    );
  }
  if (err instanceof Error) return err;
  return new Error("Error de red al contactar el servicio");
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text.slice(0, 280) || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, body: unknown, timeoutMs = 180_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    return parseJson<T>(response);
  } catch (err) {
    throw wrapFetchError(err, timeoutMs);
  } finally {
    clearTimeout(timer);
  }
}

export async function postForm<T>(
  path: string,
  form: FormData,
  timeoutMs = 120_000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    return parseJson<T>(response);
  } catch (err) {
    throw wrapFetchError(err, timeoutMs);
  } finally {
    clearTimeout(timer);
  }
}

export async function getJson<T>(path: string, timeoutMs = 30_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { signal: controller.signal });
    return parseJson<T>(response);
  } catch (err) {
    throw wrapFetchError(err, timeoutMs);
  } finally {
    clearTimeout(timer);
  }
}
