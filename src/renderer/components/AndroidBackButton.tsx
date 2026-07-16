import { useEffect } from 'react';
import { App as CapacitorApp } from '@capacitor/app';
import { isNativeMobile } from '../lib/mobile-platform';

export function AndroidBackButton() {
  useEffect(() => {
    if (!isNativeMobile()) return;
    let disposed = false;
    let removeListener: (() => Promise<void>) | null = null;

    void CapacitorApp.addListener('backButton', async ({ canGoBack }) => {
      if (canGoBack || window.history.length > 1) {
        window.history.back();
      } else {
        await CapacitorApp.minimizeApp();
      }
    }).then((handle) => {
      if (disposed) {
        void handle.remove();
      } else {
        removeListener = handle.remove;
      }
    });

    return () => {
      disposed = true;
      if (removeListener) void removeListener();
    };
  }, []);

  return null;
}
