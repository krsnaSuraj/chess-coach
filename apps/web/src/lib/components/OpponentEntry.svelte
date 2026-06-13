<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher<{move: {uci: string}}>();
  
  let moveInput = $state('');
  let error = $state('');
  
  function submitMove() {
    if (!moveInput.trim()) {
      error = 'Please enter a move';
      return;
    }
    if (!/^[a-h][1-8][a-h][1-8][nbrq]?$/.test(moveInput)) {
      error = 'Invalid move format (use UCI, e.g., e7e5)';
      return;
    }
    error = '';
    dispatch('move', { uci: moveInput });
    moveInput = '';
  }
</script>

<div class="opponent-input">
  <h3>Enter Opponent's Move</h3>
  
  <div class="input-row">
    <input
      type="text"
      bind:value={moveInput}
      placeholder="e.g., e7e5"
      on:keydown={(e: KeyboardEvent) => {
        if (e.key === 'Enter') submitMove();
      }}
    />
    <button on:click={submitMove}>Submit</button>
  </div>
  
  {#if error}
    <p class="error">{error}</p>
  {/if}
  
  <p class="hint">UCI format (e.g., e2e4, g1f3, e7e8q)</p>
</div>

<style>
  .opponent-input {
    max-width: 400px;
    margin: 1rem auto;
    padding: 1rem;
    background: #2d2d44;
    border-radius: 8px;
    color: #eee;
  }
  h3 {
    margin: 0 0 1rem;
    font-size: 0.95rem;
  }
  .input-row {
    display: flex;
    gap: 0.5rem;
  }
  input {
    flex: 1;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #555;
    border-radius: 4px;
    background: #1a1a2e;
    color: #eee;
  }
  button {
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    cursor: pointer;
    border: none;
    border-radius: 4px;
    background: #4a90d9;
    color: white;
  }
  button:hover { background: #357abd; }
  .error { color: #ef5350; margin: 0.5rem 0 0; font-size: 0.875rem; }
  .hint { color: #888; margin: 0.5rem 0 0; font-size: 0.75rem; }
</style>
