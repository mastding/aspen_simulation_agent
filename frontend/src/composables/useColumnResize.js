import { onMounted, onBeforeUnmount, ref } from 'vue';

/**
 * Composable for resizable table columns.
 * Usage:
 *   const tableRef = ref(null);
 *   useColumnResize(tableRef);
 *   <table ref="tableRef" class="gh-table resizable-table">
 */
export function useColumnResize(tableRef) {
  const handles = ref([]);
  let activeHandle = null;
  let startX = 0;
  let startWidth = 0;
  let th = null;

  function onMouseDown(e) {
    e.preventDefault();
    activeHandle = e.target;
    th = activeHandle.parentElement;
    startX = e.clientX;
    startWidth = th.offsetWidth;
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  function onMouseMove(e) {
    if (!th) return;
    const diff = e.clientX - startX;
    const newWidth = Math.max(40, startWidth + diff);
    th.style.width = newWidth + 'px';
    th.style.minWidth = newWidth + 'px';
  }

  function onMouseUp() {
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    activeHandle = null;
    th = null;
  }

  function init() {
    const table = tableRef.value;
    if (!table) return;
    const ths = table.querySelectorAll('thead th');
    ths.forEach((header, i) => {
      // Skip last column (no resize handle needed on the rightmost)
      if (i === ths.length - 1) return;
      header.style.position = 'relative';
      const handle = document.createElement('div');
      handle.className = 'col-resize-handle';
      handle.addEventListener('mousedown', onMouseDown);
      header.appendChild(handle);
      handles.value.push(handle);
    });
  }

  function cleanup() {
    handles.value.forEach(h => {
      h.removeEventListener('mousedown', onMouseDown);
      h.remove();
    });
    handles.value = [];
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  onMounted(() => {
    // Delay to ensure table is rendered
    setTimeout(init, 100);
  });

  onBeforeUnmount(cleanup);

  return { reinit: () => { cleanup(); setTimeout(init, 100); } };
}
