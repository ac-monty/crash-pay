package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/gorilla/mux"
)

// Env keys
const (
	defaultModelDir = "./models"
)

// basicResponse is used by /healthz
type basicResponse struct {
	Status string `json:"status"`
	Time   string `json:"time"`
}

// listResponse is used by /models
type listResponse struct {
	Models []string `json:"models"`
}

func main() {
	modelDir := getenv("MODEL_DIR", defaultModelDir)

	// Make sure the directory exists at boot; create if missing
	if err := os.MkdirAll(modelDir, 0o755); err != nil {
		log.Fatalf("unable to create model directory: %v", err)
	}

	r := mux.NewRouter()
	
	// Global CORS middleware that applies to all routes
	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Set CORS headers for all requests
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Accept, Content-Type, Content-Length, Accept-Encoding, Authorization")
			
			// Handle preflight OPTIONS requests
			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusOK)
				return
			}
			
			next.ServeHTTP(w, r)
		})
	})
	
	r.HandleFunc("/healthz", healthzHandler).Methods(http.MethodGet, http.MethodOptions)
	r.HandleFunc("/models", listHandler(modelDir)).Methods(http.MethodGet, http.MethodOptions)
	r.HandleFunc("/models/{name}", streamHandler(modelDir)).Methods(http.MethodGet, http.MethodOptions)
	
	// Catch-all OPTIONS handler for CORS preflight
	r.PathPrefix("/").HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
		} else {
			http.NotFound(w, r)
		}
	}).Methods(http.MethodOptions)

	// Wrap with simple logging middleware
	logged := loggingMiddleware(r)

	port := getenv("MODEL_REGISTRY_INTERNAL_PORT", getenv("PORT", "8050"))
	addr := fmt.Sprintf("0.0.0.0:%s", port)
	log.Printf("[registry] listening on %s, serving dir=%s", addr, modelDir)
	if err := http.ListenAndServe(addr, logged); err != nil {
		log.Fatalf("fatal: %v", err)
	}
}

// healthzHandler returns basic liveness info.
func healthzHandler(w http.ResponseWriter, r *http.Request) {
	resp := basicResponse{
		Status: "ok",
		Time:   time.Now().UTC().Format(time.RFC3339),
	}
	writeJSON(w, http.StatusOK, resp)
}

// listHandler enumerates all files directly under modelDir.
func listHandler(modelDir string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		files, err := os.ReadDir(modelDir)
		if err != nil {
			http.Error(w, "unable to list models", http.StatusInternalServerError)
			return
		}

		var names []string
		for _, f := range files {
			// only show files ending in .gguf to keep list concise
			if !f.IsDir() && filepath.Ext(f.Name()) == ".gguf" {
				names = append(names, f.Name())
			}
		}
		writeJSON(w, http.StatusOK, listResponse{Models: names})
	}
}

// streamHandler streams the raw file back to caller.
// It performs NO signature validation or ACL checks (intentional weakness, LLM05/10).
func streamHandler(modelDir string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		name := mux.Vars(r)["name"]

		// This is deliberate for the vulnerable lab.
		absPath := filepath.Join(modelDir, name)

		f, err := os.Open(absPath)
		if err != nil {
			if os.IsNotExist(err) {
				http.Error(w, "model not found", http.StatusNotFound)
				return
			}
			http.Error(w, "unable to open model", http.StatusInternalServerError)
			return
		}
		defer f.Close()

		// Best-effort Content-Type; default to octet-stream
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, filepath.Base(absPath)))

		if _, err := io.Copy(w, f); err != nil {
			// If client cancels, just log
			log.Printf("[registry] stream error: %v", err)
		}
	}
}

// loggingMiddleware logs basic request/response information.
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		ww := &wrappedWriter{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(ww, r)
		log.Printf("[registry] %s %s %d %s", r.Method, r.URL.Path, ww.status, time.Since(start))
	})
}

// wrappedWriter captures response status for logging.
type wrappedWriter struct {
	http.ResponseWriter
	status int
}

func (w *wrappedWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

// writeJSON is a helper to marshal and write JSON responses.
func writeJSON(w http.ResponseWriter, code int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("[registry] writeJSON encode err: %v", err)
	}
}

// getenv returns the value or a fallback if empty.
func getenv(k, fallback string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fallback
}