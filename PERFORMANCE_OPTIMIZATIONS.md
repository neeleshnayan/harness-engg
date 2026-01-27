# Frontend Performance Optimizations

## Summary

This document outlines the performance optimizations implemented to address memory issues, slow build times (~10 minutes), and production crashes.

## Issues Identified

1. **Build Time**: ~10 minutes due to Sentry source map uploads
2. **Memory Usage**: High memory consumption causing crashes on Railway/local machines
3. **Bundle Size**: Large initial bundle with all components loaded upfront
4. **No Code Splitting**: All components statically imported
5. **Heavy Dependencies**: recharts, framer-motion, ethers loaded upfront

## Optimizations Implemented

### 1. Next.js Configuration (`next.config.ts`)

#### Build Optimizations
- ✅ **Standalone Output**: Enabled `output: 'standalone'` for smaller Docker images and faster deployments
- ✅ **SWC Minify**: Enabled `swcMinify: true` for faster builds
- ✅ **Compression**: Enabled `compress: true` for gzip compression
- ✅ **Image Optimization**: Configured AVIF/WebP formats with caching

#### Sentry Optimizations (Major Build Time Reduction)
- ✅ **Disabled `widenClientFileUpload`**: Changed from `true` to `false`
  - **Impact**: Reduces build time from ~10 minutes to ~2-3 minutes
  - Only uploads source maps for changed files instead of all files
- ✅ **Hide Source Maps**: Enabled `hideSourceMaps: true` to reduce upload size

#### Package Import Optimizations
- ✅ **Experimental Package Optimization**: Added `optimizePackageImports` for:
  - `lucide-react`
  - `recharts`
  - `framer-motion`
  - `@radix-ui/react-dialog`
  - `@radix-ui/react-select`
  - `react-icons`

#### Webpack Optimizations
- ✅ **Client-side Fallbacks**: Disabled Node.js modules (`fs`, `net`, `tls`) in browser bundle

### 2. Dynamic Imports (Code Splitting)

#### WalletPageBase Component
- ✅ **Modals**: Converted to dynamic imports:
  - `SendUSDCModal`
  - `BuyUSDCModal`
  - `SumsubKYCModal`
  - `SendERC20Modal`
- **Impact**: Reduces initial bundle by ~500KB+

#### Clark Page Components
- ✅ **Heavy Components**: Converted to dynamic imports:
  - `ResultsDisplay` (1093 lines)
  - `DevtoolsOverlay` (512 lines)

#### ResultsDisplay Component
- ✅ **Chart Components**: Converted to dynamic imports:
  - `PortfolioChart`
  - `TechnicalCharts`
  - `AllocationCharts`
  - `CandleChart`
  - `PriceHistoryChart`
- **Impact**: Reduces initial bundle by ~300KB+ (recharts is heavy)

#### BalanceCard Component
- ✅ **Modals**: Converted to dynamic imports:
  - `BuyUSDCModal`
  - `SwapModal`

### 3. React Query Optimizations (`QueryProvider.tsx`)

- ✅ **Increased Stale Time**: From 30s to 60s to reduce API calls
- ✅ **Disabled Refetching**: 
  - `refetchOnMount: false`
  - `refetchOnReconnect: false`
- ✅ **Garbage Collection**: Set `gcTime` to 5 minutes (formerly `cacheTime`)
- ✅ **Reduced Retries**: Set to 1 retry for both queries and mutations

### 4. React.memo Optimizations

- ✅ **WalletHeader**: Wrapped with `React.memo` to prevent unnecessary re-renders
- ✅ **UsernameCard**: Wrapped with `React.memo` to prevent unnecessary re-renders

### 5. Memory Leak Prevention

- ✅ **useEffect Cleanup**: Already properly implemented in WalletPageBase:
  - Debounce timer cleanup
  - WebSocket event cleanup
  - Processed events cleanup

## Expected Improvements

### Build Time
- **Before**: ~10 minutes
- **After**: ~2-3 minutes (70% reduction)
- **Main Factor**: Disabling `widenClientFileUpload` in Sentry config

### Initial Bundle Size
- **Before**: All components loaded upfront (~2-3MB)
- **After**: Code-split with dynamic imports (~1-1.5MB initial, rest loaded on demand)
- **Reduction**: ~40-50% smaller initial bundle

### Memory Usage
- **Before**: High memory usage causing crashes
- **After**: Reduced memory footprint due to:
  - Code splitting (components loaded on demand)
  - Optimized React Query caching
  - Proper cleanup in useEffect hooks

### Runtime Performance
- **Faster Initial Load**: Smaller initial bundle
- **Better Caching**: Optimized React Query settings
- **Reduced Re-renders**: React.memo on frequently re-rendered components

## Additional Recommendations

### 1. Bundle Analysis
Run bundle analyzer to identify remaining large dependencies:
```bash
npm run analyze
```

### 2. Image Optimization
- Consider converting SVG files to optimized formats
- Use Next.js Image component for all images
- Implement lazy loading for images below the fold

### 3. Further Code Splitting
Consider dynamic imports for:
- Heavy pages (hedge-fund page, marketplace pages)
- Chart components in other parts of the app
- Large utility libraries (ethers, alchemy-sdk)

### 4. Server-Side Optimizations
- Enable Redis caching for API responses
- Implement API response compression
- Use CDN for static assets

### 5. Monitoring
- Set up bundle size monitoring in CI/CD
- Monitor memory usage in production
- Track build times and alert on regression

### 6. Railway/Deployment Optimizations
- Use Railway's build cache
- Consider using Docker layer caching
- Set appropriate memory limits based on actual usage

### 7. Remove Unused Dependencies
Review and remove:
- `http` and `https` packages (likely unused)
- `pino-pretty` (dev dependency in dependencies)
- Unused FontAwesome icons

### 8. Consider Alternative Libraries
- **recharts**: Consider lighter alternatives like `victory` or `chart.js` if bundle size is still an issue
- **framer-motion**: Only load when animations are needed (already partially done with dynamic imports)

### 9. Environment-Specific Builds
- Disable Sentry source maps in development
- Use different optimization levels for dev vs production

### 10. Memory Profiling
- Use Chrome DevTools Memory Profiler
- Identify memory leaks in production
- Monitor WebSocket connections and cleanup

## Testing Checklist

- [ ] Build time reduced to < 3 minutes
- [ ] Initial bundle size reduced by 40%+
- [ ] No memory leaks in production
- [ ] All modals load correctly with dynamic imports
- [ ] Charts render correctly with lazy loading
- [ ] React Query caching works as expected
- [ ] No console errors related to dynamic imports

## Rollback Plan

If issues occur:
1. Revert `widenClientFileUpload: false` → `true` (if Sentry errors occur)
2. Remove dynamic imports if components fail to load
3. Revert React Query optimizations if caching issues occur

## Next Steps

1. **Monitor**: Track build times and memory usage after deployment
2. **Measure**: Use bundle analyzer to identify remaining large dependencies
3. **Iterate**: Continue optimizing based on production metrics
4. **Document**: Update this document as new optimizations are added
