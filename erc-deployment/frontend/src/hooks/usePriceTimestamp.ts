import { useState, useEffect } from 'react';

export const usePriceTimestamp = (isFetching: boolean) => {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    if (!isFetching && lastUpdated === null) {
      // First successful fetch
      setLastUpdated(new Date());
    } else if (!isFetching && lastUpdated !== null) {
      // Subsequent successful fetches
      setLastUpdated(new Date());
    }
  }, [isFetching, lastUpdated]);

  const formatLastUpdated = () => {
    if (!lastUpdated) return 'Never updated';
    
    const now = new Date();
    const diffMs = now.getTime() - lastUpdated.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    
    if (diffSeconds < 60) {
      return `Updated ${diffSeconds}s ago`;
    } else if (diffMinutes < 60) {
      return `Updated ${diffMinutes}m ago`;
    } else {
      return `Updated at ${lastUpdated.toLocaleTimeString()}`;
    }
  };

  return {
    lastUpdated,
    formatLastUpdated,
  };
};
