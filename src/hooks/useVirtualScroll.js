/**
 * useVirtualScroll Hook
 * 
 * Custom hook for implementing virtual scrolling for large datasets.
 * Only renders items that are visible in the viewport plus a buffer.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

/**
 * Virtual scrolling hook for efficient rendering of large lists.
 * 
 * @param {Object} options - Configuration options
 * @param {number} options.itemCount - Total number of items
 * @param {number} options.itemHeight - Height of each item in pixels
 * @param {number} options.containerHeight - Height of the scrollable container
 * @param {number} options.overscan - Number of items to render outside visible area (default: 3)
 * @returns {Object} Virtual scroll state and handlers
 */
export function useVirtualScroll({
  itemCount,
  itemHeight,
  containerHeight,
  overscan = 3,
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef(null);

  // Calculate visible range
  const { startIndex, endIndex, visibleItems, totalHeight, offsetY } = useMemo(() => {
    const visibleCount = Math.ceil(containerHeight / itemHeight);
    const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const end = Math.min(itemCount - 1, start + visibleCount + 2 * overscan);
    
    return {
      startIndex: start,
      endIndex: end,
      visibleItems: end - start + 1,
      totalHeight: itemCount * itemHeight,
      offsetY: start * itemHeight,
    };
  }, [scrollTop, itemCount, itemHeight, containerHeight, overscan]);

  // Handle scroll events
  const handleScroll = useCallback((event) => {
    const { scrollTop: newScrollTop } = event.target;
    setScrollTop(newScrollTop);
  }, []);

  // Scroll to specific index
  const scrollToIndex = useCallback((index, align = 'start') => {
    if (!containerRef.current) return;

    let targetScrollTop;
    
    switch (align) {
      case 'center':
        targetScrollTop = index * itemHeight - containerHeight / 2 + itemHeight / 2;
        break;
      case 'end':
        targetScrollTop = (index + 1) * itemHeight - containerHeight;
        break;
      case 'start':
      default:
        targetScrollTop = index * itemHeight;
    }

    containerRef.current.scrollTop = Math.max(0, Math.min(targetScrollTop, totalHeight - containerHeight));
  }, [itemHeight, containerHeight, totalHeight]);

  // Get items to render
  const getVirtualItems = useCallback((items) => {
    return items.slice(startIndex, endIndex + 1).map((item, index) => ({
      item,
      index: startIndex + index,
      style: {
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: itemHeight,
        transform: `translateY(${(startIndex + index) * itemHeight}px)`,
      },
    }));
  }, [startIndex, endIndex, itemHeight]);

  // Container style
  const containerStyle = useMemo(() => ({
    height: containerHeight,
    overflow: 'auto',
    position: 'relative',
  }), [containerHeight]);

  // Inner container style (creates scrollable area)
  const innerStyle = useMemo(() => ({
    height: totalHeight,
    position: 'relative',
  }), [totalHeight]);

  return {
    containerRef,
    containerStyle,
    innerStyle,
    handleScroll,
    scrollToIndex,
    getVirtualItems,
    startIndex,
    endIndex,
    visibleItems,
    totalHeight,
    offsetY,
  };
}

/**
 * Simplified virtual scroll for dynamic height items.
 * Uses intersection observer for more flexible rendering.
 */
export function useIntersectionVirtualScroll({ rootMargin = '100px' } = {}) {
  const [visibleIndices, setVisibleIndices] = useState(new Set());
  const observerRef = useRef(null);
  const itemRefs = useRef(new Map());

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        setVisibleIndices((prev) => {
          const next = new Set(prev);
          entries.forEach((entry) => {
            const index = parseInt(entry.target.dataset.index, 10);
            if (entry.isIntersecting) {
              next.add(index);
            } else {
              next.delete(index);
            }
          });
          return next;
        });
      },
      { rootMargin }
    );

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [rootMargin]);

  const setItemRef = useCallback((index, element) => {
    if (element) {
      itemRefs.current.set(index, element);
      observerRef.current?.observe(element);
    } else {
      const existing = itemRefs.current.get(index);
      if (existing) {
        observerRef.current?.unobserve(existing);
        itemRefs.current.delete(index);
      }
    }
  }, []);

  const isVisible = useCallback((index) => {
    return visibleIndices.has(index);
  }, [visibleIndices]);

  return {
    setItemRef,
    isVisible,
    visibleIndices,
  };
}

export default useVirtualScroll;

