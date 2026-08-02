import json
import os
import numpy as np
import matplotlib.pyplot as plt

def analyze_trainer_state(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    log_history = data.get("log_history", [])
    
    # Separate training steps and evaluation steps
    train_logs = [log for log in log_history if "loss" in log]
    eval_logs = [log for log in log_history if "eval_loss" in log]

    if not train_logs:
        print("No training logs found in trainer_state.json")
        return

    steps = [log["step"] for log in train_logs]
    epochs = [log["epoch"] for log in train_logs]
    losses = [log["loss"] for log in train_logs]
    lrs = [log.get("learning_rate", 0.0) for log in train_logs]
    grad_norms = [log.get("grad_norm", 0.0) for log in train_logs]

    # Calculate statistics
    initial_loss = losses[0]
    final_loss = losses[-1]
    min_loss = min(losses)
    min_loss_step = steps[losses.index(min_loss)]
    
    # Calculate moving averages for loss
    window_size = min(50, len(losses))
    moving_avg_loss = np.convolve(losses, np.ones(window_size)/window_size, mode='valid')
    moving_avg_steps = steps[window_size - 1:]

    print("=" * 60)
    print("               TRAINER STATE ANALYSIS REPORT               ")
    print("=" * 60)
    print(f"Total Training Steps: {len(steps)}")
    print(f"Total Epochs:         {epochs[-1]:.2f}")
    print(f"Initial Loss:         {initial_loss:.4f}")
    print(f"Final Loss:           {final_loss:.4f} (Reduction: {((initial_loss - final_loss) / initial_loss) * 100:.2f}%)")
    print(f"Minimum Loss:         {min_loss:.4f} at Step {min_loss_step}")
    
    # Gradient Norm analysis
    valid_grad_norms = [g for g in grad_norms if g is not None]
    if valid_grad_norms:
        print("-" * 60)
        print("Gradient Norm Statistics:")
        print(f"  Mean Grad Norm:     {np.mean(valid_grad_norms):.4f}")
        print(f"  Max Grad Norm:      {np.max(valid_grad_norms):.4f}")
        print(f"  Min Grad Norm:      {np.min(valid_grad_norms):.4f}")
        print(f"  Std Grad Norm:      {np.std(valid_grad_norms):.4f}")
        if np.max(valid_grad_norms) > 5.0:
            print("  [ALERT] High gradient norm detected. Check for gradient spikes.")
        else:
            print("  [INFO] Gradient norms are stable (no severe spikes).")
    
    # Learning Rate analysis
    print("-" * 60)
    print("Learning Rate Analysis:")
    peak_lr = max(lrs)
    peak_lr_step = steps[lrs.index(peak_lr)]
    print(f"  Peak Learning Rate: {peak_lr:.2e} at Step {peak_lr_step}")
    print(f"  Final Learning Rate: {lrs[-1]:.2e}")

    # Plotting
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    
    # 1. Loss plot
    axes[0].plot(steps, losses, alpha=0.3, color='blue', label='Raw Loss')
    if len(moving_avg_loss) > 0:
        axes[0].plot(moving_avg_steps, moving_avg_loss, color='red', linewidth=2, label=f'Moving Avg (w={window_size})')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Training Loss Trend')
    axes[0].grid(True, linestyle='--', alpha=0.6)
    axes[0].legend()

    # 2. Gradient Norm plot
    axes[1].plot(steps, grad_norms, color='purple', alpha=0.8)
    axes[1].set_ylabel('Gradient Norm')
    axes[1].set_title('Gradient Norm (Stability Check)')
    axes[1].grid(True, linestyle='--', alpha=0.6)

    # 3. Learning Rate plot
    axes[2].plot(steps, lrs, color='green', alpha=0.8)
    axes[2].set_ylabel('Learning Rate')
    axes[2].set_xlabel('Steps')
    axes[2].set_title('Learning Rate Schedule')
    axes[2].grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plot_path = os.path.join(os.path.dirname(file_path), "trainer_state_trends.png")
    plt.savefig(plot_path, dpi=150)
    print("=" * 60)
    print(f"Analysis plots saved successfully to:\n{plot_path}")
    print("=" * 60)

if __name__ == "__main__":
    import sys
    default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trainer_state.json"))
    target_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    analyze_trainer_state(target_path)
