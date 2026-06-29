/**
 * Vercel Speed Insights Integration
 * Initializes Speed Insights for performance monitoring
 */
import { injectSpeedInsights } from 'https://cdn.jsdelivr.net/npm/@vercel/speed-insights@2.0.0/+esm';

// Initialize Speed Insights
injectSpeedInsights({
  debug: false, // Set to true for development debugging
  framework: 'fastapi'
});
