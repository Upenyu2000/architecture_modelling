import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.upenyu.roomifystudio',
  appName: 'Roomify Studio',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
  android: {
    allowMixedContent: true,
    backgroundColor: '#fdfbf7',
  },
  plugins: {
    App: {
      disableBackButtonHandler: false,
    },
  },
};

export default config;
