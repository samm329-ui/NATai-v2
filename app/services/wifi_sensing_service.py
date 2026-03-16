"""
WiFi Sensing Service - Integrates RuView WiFi DensePose functionality
Provides real-time human pose detection through WiFi signals
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import numpy as np

try:
    import torch
    import torch.nn as nn
    from torchvision import models
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not available - WiFi sensing will run in demo mode")

logger = logging.getLogger(__name__)

class WiFiSensingService:
    """Manages WiFi-based human pose detection and tracking"""
    
    def __init__(self):
        self.is_running = False
        self.sensing_active = False
        self.model = None
        self.device = "cpu"
        
        # Mock data for demo mode
        self.demo_mode = not TORCH_AVAILABLE
        self.current_detections = []
        
        # WebSocket connections for real-time streaming
        self.active_connections: List = []
        
        # Configuration
        self.config = {
            "sampling_rate": 1000,  # Hz
            "num_antennas": 3,
            "confidence_threshold": 0.5,
            "max_people": 5,
            "detection_range": 10,  # meters
        }
        
        logger.info(f"WiFi Sensing Service initialized (Demo mode: {self.demo_mode})")
    
    def initialize_model(self):
        """Initialize the WiFi DensePose model"""
        if self.demo_mode:
            logger.info("Running in demo mode - using simulated data")
            return True
        
        try:
            # In production, this would load the actual WiFi DensePose model
            # For now, we'll use a simplified version
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
            
            # Placeholder model - in real implementation, load pre-trained weights
            self.model = self._create_placeholder_model()
            self.model.to(self.device)
            self.model.eval()
            
            logger.info("WiFi sensing model initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            self.demo_mode = True
            return False
    
    def _create_placeholder_model(self):
        """Create placeholder model architecture"""
        # Simplified model for demonstration
        # Real implementation would use the actual WiFi DensePose architecture
        class SimplePoseModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.csi_encoder = nn.Sequential(
                    nn.Conv2d(3, 64, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.MaxPool2d(2),
                    nn.Conv2d(64, 128, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.MaxPool2d(2),
                    nn.Flatten(),
                    nn.Linear(128 * 56 * 56, 512),
                    nn.ReLU(),
                    nn.Linear(512, 17 * 2)  # 17 keypoints, x,y coordinates
                )
            
            def forward(self, x):
                return self.csi_encoder(x)
        
        return SimplePoseModel()
    
    async def start_sensing(self):
        """Start WiFi sensing"""
        if self.is_running:
            logger.warning("Sensing already running")
            return
        
        self.is_running = True
        self.sensing_active = True
        
        if not self.model and not self.demo_mode:
            self.initialize_model()
        
        logger.info("WiFi sensing started")
        
        # Start background task for continuous sensing
        asyncio.create_task(self._sensing_loop())
    
    async def stop_sensing(self):
        """Stop WiFi sensing"""
        self.is_running = False
        self.sensing_active = False
        logger.info("WiFi sensing stopped")
    
    async def _sensing_loop(self):
        """Main sensing loop - processes WiFi signals continuously"""
        while self.is_running:
            try:
                # Get WiFi CSI data (Channel State Information)
                csi_data = await self._get_csi_data()
                
                # Process and detect poses
                detections = await self._process_csi_data(csi_data)
                
                # Update current detections
                self.current_detections = detections
                
                # Broadcast to WebSocket clients
                await self._broadcast_detections(detections)
                
                # Sleep based on sampling rate
                await asyncio.sleep(1.0 / 30)  # 30 FPS for smooth visualization
                
            except Exception as e:
                logger.error(f"Error in sensing loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _get_csi_data(self) -> np.ndarray:
        """Get Channel State Information from WiFi hardware"""
        if self.demo_mode:
            # Generate simulated CSI data for demonstration
            return self._generate_demo_csi()
        
        # Real implementation would read from ESP32 or WiFi adapter
        # For now, return simulated data
        return self._generate_demo_csi()
    
    def _generate_demo_csi(self) -> np.ndarray:
        """Generate simulated CSI data for demo mode"""
        # Simulate CSI data: [num_antennas, num_subcarriers, time_samples]
        num_subcarriers = 56
        time_samples = 100
        
        # Add some realistic-looking noise and patterns
        csi = np.random.randn(
            self.config["num_antennas"], 
            num_subcarriers, 
            time_samples
        ) * 0.1
        
        # Add simulated human movement pattern
        t = np.linspace(0, 2 * np.pi, time_samples)
        movement = np.sin(t) * 0.5
        csi[:, :, :] += movement
        
        return csi
    
    async def _process_csi_data(self, csi_data: np.ndarray) -> List[Dict[str, Any]]:
        """Process CSI data and detect human poses"""
        if self.demo_mode:
            return self._generate_demo_detections()
        
        try:
            # Convert CSI to format expected by model
            # Real implementation would do proper CSI preprocessing
            tensor_input = torch.from_numpy(csi_data).float()
            
            # Run inference
            with torch.no_grad():
                output = self.model(tensor_input)
            
            # Post-process outputs to get pose keypoints
            detections = self._post_process_output(output)
            
            return detections
        except Exception as e:
            logger.error(f"Error processing CSI data: {e}")
            return []
    
    def _generate_demo_detections(self) -> List[Dict[str, Any]]:
        """Generate demo pose detections"""
        num_people = np.random.randint(0, 3)  # 0-2 people for demo
        detections = []
        
        for i in range(num_people):
            # Generate a realistic-looking pose
            keypoints = []
            base_x = 0.3 + i * 0.3
            base_y = 0.5
            
            # 17 COCO keypoints: nose, eyes, ears, shoulders, elbows, wrists,
            # hips, knees, ankles
            keypoint_offsets = [
                (0, -0.2),      # nose
                (-0.02, -0.22), # left eye
                (0.02, -0.22),  # right eye
                (-0.04, -0.21), # left ear
                (0.04, -0.21),  # right ear
                (-0.08, -0.1),  # left shoulder
                (0.08, -0.1),   # right shoulder
                (-0.12, 0),     # left elbow
                (0.12, 0),      # right elbow
                (-0.15, 0.1),   # left wrist
                (0.15, 0.1),    # right wrist
                (-0.06, 0.1),   # left hip
                (0.06, 0.1),    # right hip
                (-0.06, 0.3),   # left knee
                (0.06, 0.3),    # right knee
                (-0.06, 0.5),   # left ankle
                (0.06, 0.5),    # right ankle
            ]
            
            for dx, dy in keypoint_offsets:
                keypoints.append({
                    "x": base_x + dx + np.random.randn() * 0.01,
                    "y": base_y + dy + np.random.randn() * 0.01,
                    "confidence": 0.7 + np.random.rand() * 0.3
                })
            
            detections.append({
                "person_id": i,
                "keypoints": keypoints,
                "bbox": [
                    base_x - 0.15, base_y - 0.25,
                    0.3, 0.75
                ],
                "confidence": 0.85,
                "timestamp": datetime.now().isoformat()
            })
        
        return detections
    
    def _post_process_output(self, model_output: torch.Tensor) -> List[Dict[str, Any]]:
        """Post-process model output to extract pose information"""
        # Convert output to numpy
        output_np = model_output.cpu().numpy()
        
        # Reshape to keypoints
        # Assuming output is [batch, num_keypoints * 2]
        num_keypoints = 17
        keypoints_flat = output_np.reshape(-1, num_keypoints, 2)
        
        detections = []
        for person_keypoints in keypoints_flat:
            keypoints = []
            for kp in person_keypoints:
                keypoints.append({
                    "x": float(kp[0]),
                    "y": float(kp[1]),
                    "confidence": 0.8  # Would be computed from model in real impl
                })
            
            detections.append({
                "person_id": len(detections),
                "keypoints": keypoints,
                "bbox": self._compute_bbox(keypoints),
                "confidence": 0.85,
                "timestamp": datetime.now().isoformat()
            })
        
        return detections
    
    def _compute_bbox(self, keypoints: List[Dict]) -> List[float]:
        """Compute bounding box from keypoints"""
        xs = [kp["x"] for kp in keypoints]
        ys = [kp["y"] for kp in keypoints]
        
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        return [x_min, y_min, x_max - x_min, y_max - y_min]
    
    async def _broadcast_detections(self, detections: List[Dict[str, Any]]):
        """Broadcast detections to all connected WebSocket clients"""
        if not self.active_connections:
            return
        
        message = {
            "type": "pose_update",
            "timestamp": datetime.now().isoformat(),
            "detections": detections,
            "num_people": len(detections)
        }
        
        # Send to all connected clients
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)
    
    async def add_connection(self, websocket):
        """Add WebSocket connection"""
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    async def remove_connection(self, websocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current sensing status"""
        return {
            "is_running": self.is_running,
            "sensing_active": self.sensing_active,
            "demo_mode": self.demo_mode,
            "device": self.device if not self.demo_mode else "demo",
            "num_detections": len(self.current_detections),
            "active_connections": len(self.active_connections),
            "config": self.config
        }
    
    def get_current_detections(self) -> List[Dict[str, Any]]:
        """Get latest detections"""
        return self.current_detections

# Singleton instance
wifi_sensing_service = WiFiSensingService()
