export function addTodo(items, title) {
  if (!title || !title.trim()) {
    throw new Error("A todo title is required");
  }

  return [...items, { id: items.length + 1, title: title.trim(), complete: false }];
}

export function completeTodo(items, id) {
  return items.map((item) => (item.id === id ? { ...item, complete: true } : item));
}
