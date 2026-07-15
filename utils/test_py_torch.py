import torch

if __name__ == "__main__":
    print("CUDA available:", torch.cuda.is_available())
    print ("Torch environment:")
    torch.utils.collect_env.main()

try:
    import torch
    import flash_attn
    from flash_attn import flash_attn_func

    # Check available backends for SDPA
    print(f"Flash Attention available: {torch.backends.cuda.flash_sdp_enabled()}")
    print(f"Mem Efficient available: {torch.backends.cuda.math_sdp_enabled()}") 
    
    # Verify version
    print(f"Flash Attention version: {flash_attn.__version__}")
    
    # Basic functionality test
    if torch.cuda.is_available():
        q = torch.randn(2, 8, 32, 64, dtype=torch.bfloat16, device='cuda')
        k = torch.randn(2, 8, 32, 64, dtype=torch.bfloat16, device='cuda')
        v = torch.randn(2, 8, 32, 64, dtype=torch.bfloat16, device='cuda')
        
        output = flash_attn_func(q, k, v)
        print("Flash Attention test successful!")
    else:
        print("CUDA device not available!")
except ImportError as e:
    print(f"Import Error: {e}")
except RuntimeError as e:
    print(f"Runtime Error: {e}")


try:
    import triton
    import triton.language as tl

    @triton.jit
    def simple_kernel(output, n_elements, BLOCK_SIZE: tl.constexpr):
        pid = tl.program_id(0)
        block_start = pid * BLOCK_SIZE
        offsets = block_start + tl.arange(0, BLOCK_SIZE)
        mask = offsets < n_elements
        
        # Just write a constant value
        tl.store(output + offsets, 42.0, mask=mask)


    def test_simple():
        # Define output tensor
        n_elements = 1024
        output = torch.zeros(n_elements, device='cuda')
        
        # Define grid
        grid = (n_elements + 128 - 1) // 128
        
        # Launch kernel
        simple_kernel[(grid,)](output, n_elements, BLOCK_SIZE=128)
        
        # Verify results
        expected = torch.full((n_elements,), 42.0, device='cuda')
        success = torch.allclose(output, expected)
        print(f"Test passed: {success}")
        
        return output, success

    # Verify version
    print(f"Triton version: {triton.__version__}")
    
    # Basic functionality test
    if torch.cuda.is_available():
        print("Testing simple Triton kernel...")
        output, success = test_simple()
        if success:
            print("First few elements:", output[:5])
            print("Triton test successful!")
        else:            
            print("Triton test failed!")
    else:
        print("CUDA device not available!")
except ImportError as e:
    print(f"Import Error: {e}")
except RuntimeError as e:
    print(f"Runtime Error: {e}")
