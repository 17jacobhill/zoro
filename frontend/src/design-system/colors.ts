export const colors = {
  green: '#87ae73',      // Your original preferred green!
  darkGreen: '#6b8a5c',  // Your original dark green
  blue: '#5BB9C2',
  red: '#9a4e4e',
  gold: '#FDB813',
  grey: '#9e9e9e',
} as const;

export type ColorName = keyof typeof colors;
