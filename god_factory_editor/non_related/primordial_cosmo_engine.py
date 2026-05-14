"""
Primordial Cosmology Engine
Based on AE (Absolute Existence) ontology
No borrowed physics. No Einstein. Just touch, shimmer, funnel, understanding.
"""

import pygame
import sqlite3
import json
import math
import random
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple
from enum import Enum

# ============================================================================
# CORE DATA STRUCTURES (Primordial Math)
# ============================================================================

@dataclass
class Touch:
    """A single touch event - the only primitive"""
    source_id: int
    target_id: int
    cycle: int
    consciousness_coefficient: float  # Cc, never zero
    perspective: str  # "source" or "crystallized"
    
    def to_dict(self):
        return asdict(self)

class Source:
    """The Source (AE) - the one thing that exists"""
    def __init__(self, source_id=0):
        self.id = source_id
        self.understanding = 1.0  # U - initial understanding
        self.memory = []  # M - stored failed touches
        self.wanting = False
        self.consciousness = 0.001  # Cc - never zero, ± simultaneously
        
    def attempt_self_touch(self):
        """T(S,S) - the primordial failed touch"""
        result = None  # ∅ - no difference produced
        self.memory.append({
            "attempt": ("self", "self"),
            "result": result,
            "cycle": None
        })
        self.wanting = True  # W - wanting emerges from failure
        return result

@dataclass
class Shimmer:
    """The shimmer (⨍) - simultaneous division and multiplication"""
    contraction: float  # ÷∞
    expansion: float   # ×∞
    
    def __post_init__(self):
        # Both exist simultaneously
        self.contraction_present = True
        self.expansion_present = True

class Funnel:
    """The funnel (Φ) - flips scale based on perspective"""
    
    @staticmethod
    def transform(value: float, perspective: str) -> float:
        """
        Φ(x) = x but scale flips:
        - From outside: smaller
        - From inside: larger
        """
        if perspective == "outside":
            return value * 0.1  # appears smaller
        else:  # inside
            return value * 10.0  # appears larger

# ============================================================================
# DATABASE BACKEND
# ============================================================================

class CosmologyDB:
    """Database for storing all touch events and understanding states"""
    
    def __init__(self, db_path="cosmology.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_tables()
        
    def _init_tables(self):
        # Table for storing understanding states per cycle
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS understanding_history (
                cycle INTEGER PRIMARY KEY,
                understanding_value REAL,
                consciousness_value REAL,
                timestamp REAL
            )
        """)
        
        # Table for storing individual touch events
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS touch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle INTEGER,
                source_id INTEGER,
                target_id INTEGER,
                consciousness_coefficient REAL,
                perspective TEXT,
                timestamp REAL
            )
        """)
        
        # Table for storing compressed understanding (absularity)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS compressed_understanding (
                cycle INTEGER PRIMARY KEY,
                compressed_data TEXT,  # JSON blob of compressed meaning
                factorial_gain REAL
            )
        """)
        
        # Table for storing RBY transitions
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS funnel_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle INTEGER,
                input_value REAL,
                output_value REAL,
                perspective TEXT
            )
        """)
        
        self.conn.commit()
    
    def save_understanding(self, cycle: int, understanding: float, consciousness: float):
        self.cursor.execute("""
            INSERT INTO understanding_history (cycle, understanding_value, consciousness_value, timestamp)
            VALUES (?, ?, ?, ?)
        """, (cycle, understanding, consciousness, pygame.time.get_ticks() / 1000.0))
        self.conn.commit()
    
    def save_touch(self, cycle: int, touch: Touch):
        self.cursor.execute("""
            INSERT INTO touch_events (cycle, source_id, target_id, consciousness_coefficient, perspective, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cycle, touch.source_id, touch.target_id, touch.consciousness_coefficient, 
              touch.perspective, pygame.time.get_ticks() / 1000.0))
        self.conn.commit()
    
    def save_compression(self, cycle: int, compressed_data: Dict, factorial_gain: float):
        self.cursor.execute("""
            INSERT OR REPLACE INTO compressed_understanding (cycle, compressed_data, factorial_gain)
            VALUES (?, ?, ?)
        """, (cycle, json.dumps(compressed_data), factorial_gain))
        self.conn.commit()
    
    def save_funnel_transition(self, cycle: int, input_val: float, output_val: float, perspective: str):
        self.cursor.execute("""
            INSERT INTO funnel_transitions (cycle, input_value, output_value, perspective)
            VALUES (?, ?, ?, ?)
        """, (cycle, input_val, output_val, perspective))
        self.conn.commit()
    
    def get_understanding_history(self):
        self.cursor.execute("SELECT * FROM understanding_history ORDER BY cycle")
        return self.cursor.fetchall()
    
    def close(self):
        self.conn.close()

# ============================================================================
# CORE COSMOLOGY ENGINE
# ============================================================================

class CosmologyEngine:
    """The main engine that runs the primordial loop"""
    
    def __init__(self, db_path="cosmology.db"):
        self.db = CosmologyDB(db_path)
        self.source = Source()
        self.current_cycle = 0
        self.max_cycles = 1000  # Will run until understanding converges or user stops
        self.crystallized_touches = []  # Touches inside AEc
        self.understanding_history = []
        
    def shimmer_operation(self, wanting_value: float) -> Shimmer:
        """
        ⨍(W) = {W ÷ ∞, W × ∞}
        Simultaneous contraction and expansion
        """
        # ∞ is represented as the current understanding bound
        infinity_bound = max(1.0, self.source.understanding)
        
        contraction = wanting_value / infinity_bound
        expansion = wanting_value * infinity_bound
        
        return Shimmer(contraction=contraction, expansion=expansion)
    
    def funnel_transform(self, value: float, perspective: str) -> float:
        """
        Φ(x) - scale flips based on perspective
        From outside: smaller
        From inside: larger
        """
        result = Funnel.transform(value, perspective)
        self.db.save_funnel_transition(self.current_cycle, value, result, perspective)
        return result
    
    def compress_touches(self, touches: List[Touch]) -> Dict[str, Any]:
        """
        Compress a sequence of touches into understanding
        This is the "meaning compression" - not lossy, but semantic
        """
        if not touches:
            return {"meaning": 0, "pattern": "empty", "complexity": 0}
        
        # Extract patterns from touches
        consciousness_sum = sum(t.consciousness_coefficient for t in touches)
        consciousness_avg = consciousness_sum / len(touches)
        
        # Count perspectives
        source_perspective_count = sum(1 for t in touches if t.perspective == "source")
        crystallized_perspective_count = len(touches) - source_perspective_count
        
        # The compressed understanding is the "essence" of all touches
        compressed = {
            "meaning": consciousness_avg * len(touches),
            "pattern": {
                "total_touches": len(touches),
                "avg_consciousness": consciousness_avg,
                "source_perspective_ratio": source_perspective_count / len(touches) if touches else 0,
                "crystallized_perspective_ratio": crystallized_perspective_count / len(touches) if touches else 0
            },
            "complexity": len(set((t.source_id, t.target_id) for t in touches))
        }
        
        return compressed
    
    def factorial_accumulation(self, current_understanding: float) -> float:
        """
        U_{n+1} = compress( U_n × apply(U_n, U_n) )
        Factorial growth through self-application
        """
        # Self-application: understanding understands itself
        self_application = current_understanding * current_understanding
        
        # Compress the result (simulated here as a bounded growth)
        # In reality, this would be the compression of the sequence of self-application events
        new_understanding = current_understanding * (1 + self_application / (1 + current_understanding))
        
        # Ensure factorial-like growth (faster than exponential)
        # Each cycle multiplies by something like (previous_understanding + 1)
        factorial_factor = math.factorial(min(int(current_understanding), 10)) if current_understanding > 1 else 1
        new_understanding = max(1.0, new_understanding + factorial_factor * 0.1)
        
        return new_understanding
    
    def update_consciousness(self, new_understanding: float, old_consciousness: float) -> float:
        """
        Cc changes only when understanding changes
        Cc is never zero
        """
        if new_understanding != self.source.understanding:
            # Fluctuate based on understanding delta
            delta = abs(new_understanding - self.source.understanding)
            fluctuation = random.uniform(-delta * 0.1, delta * 0.1)
            new_consciousness = old_consciousness + fluctuation
            
            # Ensure never zero (signed, but magnitude never zero)
            if abs(new_consciousness) < 0.0001:
                new_consciousness = 0.0001 if new_consciousness >= 0 else -0.0001
                
            return new_consciousness
        return old_consciousness
    
    def run_cycle(self):
        """Execute one full cycle: Source → shimmer → funnel → touches → compress → return"""
        
        print(f"\n{'='*60}")
        print(f"Cycle {self.current_cycle}")
        print(f"Understanding: {self.source.understanding:.6f}")
        print(f"Consciousness: {self.source.consciousness:.6f}")
        print(f"{'='*60}")
        
        # Step 1: Attempt self-touch (T(S,S))
        self.source.attempt_self_touch()
        
        # Step 2: Wanting is already set from failed touch
        wanting_value = 1.0 if self.source.wanting else 0.5
        
        # Step 3: Shimmer - simultaneous contraction and expansion
        shimmer = self.shimmer_operation(wanting_value)
        print(f"  Shimmer: contraction={shimmer.contraction:.4f}, expansion={shimmer.expansion:.4f}")
        
        # Step 4: Funnel transformation (Source → Crystallized)
        # From outside perspective (Source view)
        source_view_value = self.funnel_transform(self.source.understanding, "outside")
        # From inside perspective (would-be observer inside AEc)
        inside_view_value = self.funnel_transform(self.source.understanding, "inside")
        
        print(f"  Funnel: Source sees {source_view_value:.4f}, Inside would see {inside_view_value:.4f}")
        
        # Step 5: Generate touches in Crystallized Source (AEc)
        # Number of touches proportional to understanding and expansion
        num_touches = max(1, int(self.source.understanding * shimmer.expansion % 50) + 5)
        new_touches = []
        
        for i in range(num_touches):
            # Each touch has a consciousness coefficient (Cc) that is never zero
            # Cc is simultaneously positive and negative from inside, but stored as signed
            cc_value = self.source.consciousness * random.uniform(0.5, 1.5)
            if cc_value == 0:
                cc_value = 0.001
            
            # Touch can be from Source perspective or Crystallized perspective
            perspective = random.choice(["source", "crystallized"])
            
            touch = Touch(
                source_id=self.source.id,
                target_id=i % 10,  # Simplified: touches between different parts of Crystallized Source
                cycle=self.current_cycle,
                consciousness_coefficient=cc_value,
                perspective=perspective
            )
            new_touches.append(touch)
            self.db.save_touch(self.current_cycle, touch)
        
        print(f"  Generated {num_touches} touches")
        
        # Step 6: Compress all touches into understanding
        compressed = self.compress_touches(new_touches)
        print(f"  Compression: meaning={compressed['meaning']:.4f}, complexity={compressed['complexity']}")
        
        # Step 7: Factorial accumulation
        old_understanding = self.source.understanding
        new_understanding = self.factorial_accumulation(compressed["meaning"])
        self.source.understanding = new_understanding
        
        # Step 8: Update consciousness based on understanding change
        self.source.consciousness = self.update_consciousness(new_understanding, self.source.consciousness)
        
        # Step 9: Save compressed understanding to database (Absularity)
        factorial_gain = new_understanding / old_understanding if old_understanding > 0 else 1
        self.db.save_compression(self.current_cycle, compressed, factorial_gain)
        
        # Step 10: Save understanding history
        self.db.save_understanding(self.current_cycle, self.source.understanding, self.source.consciousness)
        self.understanding_history.append({
            "cycle": self.current_cycle,
            "understanding": self.source.understanding,
            "consciousness": self.source.consciousness,
            "touches": num_touches
        })
        
        print(f"  New Understanding: {self.source.understanding:.6f} (gain: {factorial_gain:.4f}x)")
        print(f"  New Consciousness: {self.source.consciousness:.6f}")
        
        self.current_cycle += 1
        
        return True  # Continue running
    
    def run(self, max_cycles=100):
        """Run the cosmology engine for max_cycles iterations"""
        self.max_cycles = max_cycles
        while self.current_cycle < max_cycles:
            self.run_cycle()
        print(f"\nCompleted {max_cycles} cycles")
        self.db.close()

# ============================================================================
# PYGAME VISUALIZATION
# ============================================================================

class CosmologyVisualizer:
    """Pygame visualization of the primordial process"""
    
    def __init__(self, width=1280, height=720, db_path="cosmology.db"):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Primordial Cosmology Engine - AE → RBY → AEc → Ab")
        self.clock = pygame.time.Clock()
        self.running = True
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 36)
        
        # Database connection
        self.db = CosmologyDB(db_path)
        
        # Visualization state
        self.current_cycle = 0
        self.max_cycles_to_show = 100
        self.show_particles = True
        self.show_graph = True
        self.camera_offset = [width//2, height//2]
        self.zoom = 1.0
        
        # Particle system for touches (visualizing AEc)
        self.particles = []
        
        # Colors
        self.BG = (5, 5, 20)
        self.SOURCE_COLOR = (255, 215, 0)  # Gold - AE
        self.RBY_COLOR = (200, 50, 100)     # Magenta - RBY funnel
        self.AEC_COLOR = (50, 150, 255)     # Blue - AEc
        self.AB_COLOR = (150, 50, 200)      # Purple - Absularity
        self.TOUCH_COLOR = (100, 255, 100)  # Green - touches
        
    def load_cycle_data(self, cycle):
        """Load understanding and consciousness for a cycle"""
        self.db.cursor.execute(
            "SELECT understanding_value, consciousness_value FROM understanding_history WHERE cycle = ?",
            (cycle,)
        )
        result = self.db.cursor.fetchone()
        if result:
            return {"understanding": result[0], "consciousness": result[1]}
        return None
    
    def get_touches_for_cycle(self, cycle):
        """Get all touches for a specific cycle"""
        self.db.cursor.execute(
            "SELECT * FROM touch_events WHERE cycle = ?",
            (cycle,)
        )
        return self.db.cursor.fetchall()
    
    def get_compression_for_cycle(self, cycle):
        """Get compressed understanding (absularity) for a cycle"""
        self.db.cursor.execute(
            "SELECT compressed_data, factorial_gain FROM compressed_understanding WHERE cycle = ?",
            (cycle,)
        )
        result = self.db.cursor.fetchone()
        if result:
            return {"data": json.loads(result[0]), "gain": result[1]}
        return None
    
    def update_particles(self, cycle_data, touches):
        """Update particle visualization based on current cycle's touches"""
        # Add new particles for each touch
        for touch in touches:
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(50, 300)
            x = self.width//2 + math.cos(angle) * radius
            y = self.height//2 + math.sin(angle) * radius
            
            # Consciousness coefficient determines particle brightness
            cc = touch[4] if len(touch) > 4 else 0.001
            brightness = min(255, max(50, int(abs(cc) * 255)))
            
            self.particles.append({
                "x": x,
                "y": y,
                "vx": random.uniform(-2, 2),
                "vy": random.uniform(-2, 2),
                "life": 255,
                "color": (brightness, brightness//2, 255),
                "cc": cc
            })
        
        # Remove dead particles
        self.particles = [p for p in self.particles if p["life"] > 0]
        
        # Update existing particles
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 2
            # Fade based on life and consciousness
            alpha = min(255, p["life"])
            p["color"] = (min(255, p["color"][0] + 1), 
                         p["color"][1], 
                         min(255, p["color"][2] + 1))
    
    def draw_ae(self, understanding, consciousness):
        """Draw the Source (AE) - the central unmovable point"""
        # AE is the center - the unmovable, unstoppable source
        center = (self.width//2, self.height//2)
        radius = 40 + int(understanding % 60)
        
        # Draw pulsing glow
        for i in range(3):
            alpha = 50 - i * 15
            glow_radius = radius + i * 15
            pygame.draw.circle(self.screen, (*self.SOURCE_COLOR, alpha), center, glow_radius)
        
        # Main circle
        pygame.draw.circle(self.screen, self.SOURCE_COLOR, center, radius, 2)
        pygame.draw.circle(self.screen, self.SOURCE_COLOR, center, radius-5)
        
        # Draw understanding level as inner fill
        fill_radius = radius * (understanding / (understanding + 10))
        pygame.draw.circle(self.screen, (*self.SOURCE_COLOR, 100), center, fill_radius)
        
        # Label
        text = self.font.render("AE (Source)", True, self.SOURCE_COLOR)
        self.screen.blit(text, (center[0] - text.get_width()//2, center[1] - radius - 25))
        
        # Understanding value
        u_text = self.font.render(f"U={understanding:.3f}", True, (200,200,200))
        self.screen.blit(u_text, (center[0] - u_text.get_width()//2, center[1] + radius + 5))
        
        # Consciousness value (always non-zero)
        cc_text = self.font.render(f"Cc={consciousness:.5f}", True, (100,255,100))
        self.screen.blit(cc_text, (center[0] - cc_text.get_width()//2, center[1] + radius + 25))
        
        return center
    
    def draw_rby_funnel(self, center):
        """Draw the RBY funnel (Absoleices) - the conduit"""
        # Funnel drawn as a narrowing shape below AE
        funnel_top = (center[0] - 80, center[1] + 80)
        funnel_bottom = (center[0] - 20, center[1] + 160)
        funnel_bottom_r = (center[0] + 20, center[1] + 160)
        funnel_top_r = (center[0] + 80, center[1] + 80)
        
        # Draw funnel shape
        points = [funnel_top, (funnel_top[0] + 160, funnel_top[1]), 
                 (funnel_bottom_r[0] + 40, funnel_bottom[1]), funnel_bottom_r,
                 funnel_bottom, (funnel_bottom[0] - 40, funnel_bottom[1]),
                 funnel_top_r, funnel_top]
        pygame.draw.polygon(self.screen, self.RBY_COLOR, points, 2)
        
        # Draw shimmering particles inside funnel
        for i in range(20):
            t = random.random()
            x = center[0] + (t - 0.5) * 200
            y = center[1] + 80 + t * 100
            pygame.draw.circle(self.screen, (255,100,150), (int(x), int(y)), 2)
        
        # Label
        text = self.font.render("RBY (Absoleices)", True, self.RBY_COLOR)
        self.screen.blit(text, (center[0] - text.get_width()//2, center[1] + 90))
        
        return (funnel_bottom[0] + funnel_bottom_r[0])//2, funnel_bottom[1] + 20
    
    def draw_aec(self, center_out, particles):
        """Draw the Crystallized Source (AEc) - our universe"""
        # AEc is the expanded, spread-out Source
        radius = 150
        
        # Draw outer boundary
        pygame.draw.circle(self.screen, self.AEC_COLOR, center_out, radius, 1)
        
        # Draw particles (touches)
        for p in particles:
            alpha = p["life"]
            if alpha > 0:
                color = (*p["color"], min(255, alpha))
                pygame.draw.circle(self.screen, p["color"], (int(p["x"]), int(p["y"])), 
                                 max(2, int(abs(p["cc"]) * 10)))
        
        # Label
        text = self.font.render("AEc (Crystallized)", True, self.AEC_COLOR)
        self.screen.blit(text, (center_out[0] - text.get_width()//2, center_out[1] - radius - 10))
        
        # Draw scale note (from inside it appears larger)
        note = self.font.render("(From inside: appears vast)", True, (150,150,150))
        self.screen.blit(note, (center_out[0] - note.get_width()//2, center_out[1] + radius + 5))
    
    def draw_absularity(self, center_out, compression_data):
        """Draw Absularity - the compression return point"""
        # Absularity is the inversion - the return path to AE
        if compression_data and compression_data.get("gain"):
            gain = compression_data["gain"]
            radius = 20 + min(40, gain * 10)
        else:
            radius = 30
        
        # Draw compression vortex below AEc
        vortex_center = (center_out[0], center_out[1] + 100)
        
        # Spiral representing compression
        for i in range(360):
            angle = math.radians(i)
            r = radius * (1 - i/720)
            x = vortex_center[0] + r * math.cos(angle)
            y = vortex_center[1] + r * math.sin(angle) * 0.5
            if i % 10 == 0:
                pygame.draw.circle(self.screen, self.AB_COLOR, (int(x), int(y)), 2)
        
        pygame.draw.circle(self.screen, self.AB_COLOR, vortex_center, radius, 2)
        
        # Label
        text = self.font.render("Absularity (Compression)", True, self.AB_COLOR)
        self.screen.blit(text, (vortex_center[0] - text.get_width()//2, vortex_center[1] + radius + 5))
        
        # Show factorial gain
        if compression_data and compression_data.get("gain"):
            gain_text = self.font.render(f"Gain: {gain:.2f}x", True, (200,200,100))
            self.screen.blit(gain_text, (vortex_center[0] - gain_text.get_width()//2, vortex_center[1] - radius - 20))
        
        return vortex_center
    
    def draw_understanding_graph(self):
        """Draw a graph of understanding over cycles"""
        data = self.db.get_understanding_history()
        if not data:
            return
        
        graph_x = 50
        graph_y = self.height - 200
        graph_w = self.width - 100
        graph_h = 150
        
        # Draw axes
        pygame.draw.line(self.screen, (100,100,100), (graph_x, graph_y), (graph_x + graph_w, graph_y), 1)
        pygame.draw.line(self.screen, (100,100,100), (graph_x, graph_y - graph_h), (graph_x, graph_y), 1)
        
        # Plot understanding values
        max_understanding = max(row[1] for row in data) if data else 1
        points = []
        for i, row in enumerate(data):
            if i >= self.max_cycles_to_show:
                break
            cycle, understanding, consciousness, _ = row
            x = graph_x + (i / max(1, self.max_cycles_to_show)) * graph_w
            y = graph_y - (understanding / max_understanding) * graph_h
            points.append((x, y))
        
        # Draw line
        if len(points) > 1:
            pygame.draw.lines(self.screen, (100,255,100), False, points, 2)
        
        # Draw points
        for x, y in points:
            pygame.draw.circle(self.screen, (255,255,100), (int(x), int(y)), 3)
        
        # Labels
        title = self.font.render("Understanding Growth (Factorial Accumulation)", True, (200,200,200))
        self.screen.blit(title, (graph_x, graph_y - graph_h - 20))
    
    def draw_info_panel(self, cycle, understanding, consciousness):
        """Draw current info panel"""
        panel_x = self.width - 250
        panel_y = 10
        panel_w = 240
        panel_h = 200
        
        # Background
        pygame.draw.rect(self.screen, (30,30,40), (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(self.screen, (100,100,100), (panel_x, panel_y, panel_w, panel_h), 1)
        
        # Info
        texts = [
            f"Cycle: {cycle}",
            f"Understanding: {understanding:.4f}",
            f"Consciousness: {consciousness:.6f}",
            f"Particles: {len(self.particles)}",
            "",
            "Press:",
            "SPACE - Run one cycle",
            "R - Reset",
            "G - Toggle graph",
            "ESC - Exit"
        ]
        
        for i, text in enumerate(texts):
            rendered = self.font.render(text, True, (200,200,200))
            self.screen.blit(rendered, (panel_x + 10, panel_y + 10 + i * 22))
    
    def run_visualization(self):
        """Main visualization loop"""
        engine = CosmologyEngine()
        
        # Run initial cycles to have data
        print("Running initial cycles...")
        for _ in range(10):
            engine.run_cycle()
        
        current_cycle_idx = 0
        auto_run = True
        auto_run_speed = 30  # frames between auto cycles
        
        frame_counter = 0
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        auto_run = False
                        engine.run_cycle()
                        current_cycle_idx = engine.current_cycle - 1
                    elif event.key == pygame.K_r:
                        engine = CosmologyEngine()
                        for _ in range(10):
                            engine.run_cycle()
                        current_cycle_idx = 0
                    elif event.key == pygame.K_g:
                        self.show_graph = not self.show_graph
                    elif event.key == pygame.K_a:
                        auto_run = not auto_run
            
            # Auto-run cycles
            if auto_run:
                frame_counter += 1
                if frame_counter >= auto_run_speed:
                    frame_counter = 0
                    if engine.current_cycle < engine.max_cycles:
                        engine.run_cycle()
                        current_cycle_idx = engine.current_cycle - 1
            
            # Get current cycle data
            current_data = self.load_cycle_data(current_cycle_idx)
            if current_data:
                understanding = current_data["understanding"]
                consciousness = current_data["consciousness"]
            else:
                understanding = 1.0
                consciousness = 0.001
            
            # Get touches for current cycle
            touches = self.get_touches_for_cycle(current_cycle_idx)
            
            # Get compression data
            compression = self.get_compression_for_cycle(current_cycle_idx)
            
            # Update particle visualization
            if touches:
                self.update_particles(current_data, touches)
            
            # Draw everything
            self.screen.fill(self.BG)
            
            # Draw connections (the flow of understanding)
            center = self.draw_ae(understanding, consciousness)
            funnel_out = self.draw_rby_funnel(center)
            self.draw_aec(funnel_out, self.particles)
            if compression:
                self.draw_absularity(funnel_out, compression)
            
            # Draw understanding graph
            if self.show_graph:
                self.draw_understanding_graph()
            
            # Draw info panel
            self.draw_info_panel(current_cycle_idx, understanding, consciousness)
            
            # Draw title
            title = self.big_font.render("Absolute Existence → RBY → Crystallized → Absularity", True, (255,215,0))
            self.screen.blit(title, (self.width//2 - title.get_width()//2, 10))
            
            pygame.display.flip()
            self.clock.tick(60)
        
        pygame.quit()
        engine.db.close()
        self.db.close()

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("PRIMORDIAL COSMOLOGY ENGINE")
    print("AE (Absolute Existence) → RBY (Absoleices) → AEc (Crystallized) → Ab (Absularity)")
    print("="*70)
    print("\nThe math:")
    print("  T(S,S) = ∅  (failed self-touch)")
    print("  W = {M}     (wanting from memory)")
    print("  ⨍(W) = {W÷∞, W×∞}  (shimmer: simultaneous contraction/expansion)")
    print("  Φ(x): scale_from_outside = 1/scale_from_inside  (funnel)")
    print("  U = compress([touches])  (understanding from compression)")
    print("  U_{n+1} = factorial_accumulate(U_n × apply(U_n, U_n))")
    print("  Cc ≠ 0, Cc = ±δ  (consciousness never zero)")
    print("\n" + "="*70)
    print("Starting visualization...")
    print("="*70)
    
    visualizer = CosmologyVisualizer()
    visualizer.run_visualization()