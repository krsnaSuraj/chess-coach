<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher<{select: {side: string; rating: number; classical: number; aggression: number}}>();
  
  let rating = $state(1500);
  let classical = $state(0.5);
  let aggression = $state(0.5);
  
  function selectSide(side: string) {
    dispatch('select', { side, rating, classical, aggression });
  }
</script>

<div class="modal-overlay">
  <div class="modal">
    <h2>Select Your Side</h2>
    
    <div class="settings">
      <label>
        Rating: {rating}
        <input type="range" min="800" max="2500" step="100" bind:value={rating} />
      </label>
      
      <label>
        Style: {classical < 0.3 ? 'Hypermodern' : classical > 0.7 ? 'Classical' : 'Balanced'}
        <input type="range" min="0" max="1" step="0.1" bind:value={classical} />
      </label>
      
      <label>
        Aggression: {aggression < 0.3 ? 'Positional' : aggression > 0.7 ? 'Tactical' : 'Balanced'}
        <input type="range" min="0" max="1" step="0.1" bind:value={aggression} />
      </label>
    </div>
    
    <div class="buttons">
      <button class="btn-white" on:click={() => selectSide('w')}>Play as White</button>
      <button class="btn-black" on:click={() => selectSide('b')}>Play as Black</button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .modal {
    background: #1a1a2e;
    color: #eee;
    padding: 2rem;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    max-width: 400px;
    width: 90%;
  }
  h2 {
    margin: 0 0 1.5rem;
    text-align: center;
    font-size: 1.4rem;
  }
  .settings {
    margin-bottom: 1.5rem;
  }
  label {
    display: block;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  input[type="range"] {
    width: 100%;
    margin-top: 0.25rem;
  }
  .buttons {
    display: flex;
    gap: 1rem;
  }
  button {
    flex: 1;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    cursor: pointer;
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
  }
  .btn-white { background: #e8e8e8; color: #1a1a2e; }
  .btn-black { background: #2d2d44; border: 1px solid #555; }
  button:hover { opacity: 0.9; }
</style>
