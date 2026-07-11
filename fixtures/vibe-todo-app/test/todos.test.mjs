import assert from "node:assert/strict";
import { addTodo, completeTodo } from "../src/todos.js";

const todos = addTodo([], "Ship OhMyCodex");
assert.equal(todos.length, 1);
assert.equal(completeTodo(todos, 1)[0].complete, true);
