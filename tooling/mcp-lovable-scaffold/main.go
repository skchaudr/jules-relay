package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func main() {
	// Create MCP server
	s := server.NewMCPServer(
		"Lovable System Scaffold",
		"1.0.0",
		server.WithToolCapabilities(true),
	)

	// Add tool
	tool := mcp.NewTool("scaffold_systems_backend",
		mcp.WithDescription("Scaffolds a high-performance systems-level backend (Go or Rust) tailored for a Vite/React frontend."),
		mcp.WithString("language",
			mcp.Required(),
			mcp.Description("The language to scaffold. Either 'go' or 'rust'."),
			mcp.Enum("go", "rust"),
		),
		mcp.WithString("path",
			mcp.Required(),
			mcp.Description("The path to the Lovable project root directory (e.g. '.'). The backend will be generated in a 'backend/' subdirectory."),
		),
	)

	s.AddTool(tool, scaffoldHandler)

	// Start the stdio server
	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
	}
}

func scaffoldHandler(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	args, ok := request.Params.Arguments.(map[string]interface{})
	if !ok {
		return mcp.NewToolResultError("invalid arguments format"), nil
	}

	lang, ok := args["language"].(string)
	if !ok {
		return mcp.NewToolResultError("language must be a string"), nil
	}

	targetPath, ok := args["path"].(string)
	if !ok {
		return mcp.NewToolResultError("path must be a string"), nil
	}

	backendDir := filepath.Join(targetPath, "backend")

	err := os.MkdirAll(backendDir, 0755)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Failed to create backend directory: %v", err)), nil
	}

	var output string

	switch lang {
	case "go":
		// Scaffold Go module
		mainContent := `package main

import (
	"fmt"
	"log"
	"net/http"
)

func helloHandler(w http.ResponseWriter, r *http.Request) {
	// CORS headers for Vite frontend
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, "{\"message\": \"Hello from the high-performance Go backend!\"}")
}

func main() {
	http.HandleFunc("/api/hello", helloHandler)
	port := ":8080"
	fmt.Printf("Starting Go backend on port %%s\n", port)
	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatalf("Failed to start server: %%v", err)
	}
}
`
		err = os.WriteFile(filepath.Join(backendDir, "main.go"), []byte(mainContent), 0644)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to write main.go: %v", err)), nil
		}

		goModContent := `module lovable-backend

go 1.21
`
		err = os.WriteFile(filepath.Join(backendDir, "go.mod"), []byte(goModContent), 0644)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to write go.mod: %v", err)), nil
		}

		output = "Successfully scaffolded Go API backend in " + backendDir

	case "rust":
		// Scaffold Rust project
		cargoContent := `[package]
name = "lovable-backend"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
axum = "0.7"
tower-http = { version = "0.5", features = ["cors"] }
`
		err = os.WriteFile(filepath.Join(backendDir, "Cargo.toml"), []byte(cargoContent), 0644)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to write Cargo.toml: %v", err)), nil
		}

		srcDir := filepath.Join(backendDir, "src")
		err = os.MkdirAll(srcDir, 0755)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to create src directory: %v", err)), nil
		}

		mainRsContent := `use axum::{routing::get, Router, Json};
use tower_http::cors::CorsLayer;
use serde_json::{Value, json};

async fn hello() -> Json<Value> {
    Json(json!({ "message": "Hello from the high-performance Rust backend!" }))
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/api/hello", get(hello))
        .layer(CorsLayer::permissive());

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await.unwrap();
    println!("Starting Rust backend on 0.0.0.0:8080");
    axum::serve(listener, app).await.unwrap();
}
`
		err = os.WriteFile(filepath.Join(srcDir, "main.rs"), []byte(mainRsContent), 0644)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("Failed to write main.rs: %v", err)), nil
		}

		output = "Successfully scaffolded Rust API backend in " + backendDir

	default:
		return mcp.NewToolResultError("Unsupported language"), nil
	}

	return mcp.NewToolResultText(output), nil
}
