/**
 * PWA Detection and Utilities
 * Detect if app is running in PWA/standalone mode
 */

/**
 * Detect if app is running in PWA/standalone mode
 */
export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  
  // iOS Safari
  if ((window.navigator as any).standalone === true) {
    return true;
  }
  
  // Android/Chrome
  if (window.matchMedia('(display-mode: standalone)').matches) {
    return true;
  }
  
  // Fallback: check if manifest exists and was likely installed
  return false;
}

/**
 * Get safe area insets (returns 0 if not available)
 */
export function getSafeAreaInsets() {
  if (typeof window === 'undefined') {
    return { top: 0, bottom: 0, left: 0, right: 0 };
  }
  
  const style = getComputedStyle(document.documentElement);
  
  return {
    top: parseInt(style.getPropertyValue('env(safe-area-inset-top)') || '0', 10),
    bottom: parseInt(style.getPropertyValue('env(safe-area-inset-bottom)') || '0', 10),
    left: parseInt(style.getPropertyValue('env(safe-area-inset-left)') || '0', 10),
    right: parseInt(style.getPropertyValue('env(safe-area-inset-right)') || '0', 10),
  };
}

/**
 * Check if device is iOS
 */
export function isIOS(): boolean {
  if (typeof window === 'undefined') return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || 
         (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

/**
 * Check if device is Android
 */
export function isAndroid(): boolean {
  if (typeof window === 'undefined') return false;
  return /Android/.test(navigator.userAgent);
}

