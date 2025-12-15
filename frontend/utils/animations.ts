/**
 * Animation Utilities
 * Framer Motion variants for smooth transitions
 */

export const springConfig = {
  type: 'spring' as const,
  damping: 20,
  stiffness: 300
};

export const composerTransition = {
  hero: {
    initial: { scale: 1, y: 0, opacity: 1 },
    exit: { scale: 0.95, y: 20, opacity: 0 },
    transition: { duration: 0.3, ease: 'easeInOut' }
  },
  bottom: {
    initial: { y: 100, opacity: 0 },
    animate: { y: 0, opacity: 1 },
    transition: { ...springConfig, delay: 0.1 }
  }
};

export const boardDockAnimation = {
  initial: { height: 0, opacity: 0 },
  animate: { height: 'auto', opacity: 1 },
  exit: { height: 0, opacity: 0 },
  transition: { duration: 0.3, ease: 'easeInOut' }
};

export const messageAnimation = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.2 }
};

export const curtainAnimation = {
  initial: { x: -320, opacity: 0 },
  animate: { x: 0, opacity: 1 },
  exit: { x: -320, opacity: 0 },
  transition: { ...springConfig }
};

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 }
};

export const rotatingExamples = {
  initial: { opacity: 0, y: -10 },
  animate: { opacity: 0.5, y: 0 },
  exit: { opacity: 0, y: 10 },
  transition: { duration: 0.6, ease: 'easeInOut' }
};

