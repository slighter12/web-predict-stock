<script lang="ts">
  export let label: string;
  export let value: string;
  export let tone: "neutral" | "positive" | "negative" = "neutral";
</script>

<article class:tone-positive={tone === "positive"} class:tone-negative={tone === "negative"}>
  <p>{label}</p>
  <strong>{value}</strong>
</article>

<style>
  article {
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 18px;
    padding: 1rem;
    background:
      linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(3, 7, 18, 0.92)),
      var(--panel);
    min-height: 112px;
  }

  p {
    margin: 0 0 0.65rem;
    color: var(--muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  strong {
    font-size: clamp(1.4rem, 2vw, 2rem);
    line-height: 1.1;
  }

  .tone-positive strong {
    color: var(--accent-positive);
  }

  .tone-negative strong {
    color: var(--accent-negative);
  }
</style>
