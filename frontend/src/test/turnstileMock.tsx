import { useEffect } from 'react';

/**
 * Stand-in for @marsidev/react-turnstile's <Turnstile>: reports a token as
 * soon as it mounts, like the real widget does with Cloudflare's test key.
 */
export function Turnstile({ onSuccess }: { onSuccess?: (token: string) => void }) {
  useEffect(() => {
    onSuccess?.('test-turnstile-token');
  }, [onSuccess]);
  return null;
}
