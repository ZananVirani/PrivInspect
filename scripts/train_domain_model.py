#!/usr/bin/env python3
"""
Domain Risk Model Training Script

This script downloads DuckDuckGo TrackerRadar data, extracts domain features,
and trains a gradient boosted regressor to predict tracking intensity.

Usage:
    python scripts/train_domain_model.py --tracker-radar-path ./data/tracker-radar
    python scripts/train_domain_model.py --out-model-path ./models/custom_model.pkl
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.ensemble import HistGradientBoostingRegressor
from scipy.stats import spearmanr
import joblib

# Try to import LightGBM and XGBoost, fallback to sklearn if not available
try:
    import lightgbm as lgb
    # Test if LightGBM can actually be used (common macOS OpenMP issue)
    try:
        test_model = lgb.LGBMRegressor(n_estimators=1, verbose=-1)
        test_model.fit([[1, 2], [3, 4]], [1, 2])
        HAS_LIGHTGBM = True
        print("✅ LightGBM available and working")
    except Exception as e:
        print(f"⚠️  LightGBM installed but not working: {e}")
        print("   This is often due to missing OpenMP on macOS")
        print("   To fix: brew install libomp")
        print("   Falling back to scikit-learn models")
        HAS_LIGHTGBM = False
except ImportError:
    print("⚠️  LightGBM not available")
    HAS_LIGHTGBM = False

try:
    import xgboost as xgb
    HAS_XGBOOST = True
    print("✅ XGBoost available")
except ImportError:
    print("⚠️  XGBoost not available")
    HAS_XGBOOST = False

if not HAS_LIGHTGBM and not HAS_XGBOOST:
    print("📦 Using scikit-learn HistGradientBoostingRegressor as fallback")

class TrackerRadarParser:
    """Parser for DuckDuckGo TrackerRadar domain JSON files"""
    
    def __init__(self, radar_path: str):
        self.radar_path = Path(radar_path)
        self.domains_path = self.radar_path / "domains"
        
    def clone_tracker_radar(self, target_path: str) -> bool:
        """Clone TrackerRadar repository if it doesn't exist"""
        target = Path(target_path)
        if target.exists():
            print(f"TrackerRadar already exists at {target}")
            return True
            
        print(f"Cloning TrackerRadar to {target}...")
        try:
            subprocess.run([
                "git", "clone", 
                "https://github.com/duckduckgo/tracker-radar.git", 
                str(target)
            ], check=True)
            print("Successfully cloned TrackerRadar repository")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone TrackerRadar: {e}")
            return False
    
    def parse_domain_json(self, json_path: Path) -> Optional[Dict]:
        """Parse a single domain JSON file and extract features"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            domain_name = json_path.stem
            
            # Get base fingerprinting score
            base_fingerprinting = data.get('fingerprinting', 0)
            
            # Create category-based tracking score
            categories = data.get('categories', [])
            tracking_categories = [
                'Ad Motivated Tracking', 'Advertising', 'Analytics', 
                'Audience Measurement', 'Third-Party Analytics Marketing',
                'Cross-site Tracking', 'Fingerprinting'
            ]
            
            # Count how many tracking categories this domain has
            tracking_category_count = sum(1 for cat in categories if cat in tracking_categories)
            category_tracking_score = min(3, tracking_category_count)  # Cap at 3
            
            # Combine fingerprinting with category-based score
            # Use max to ensure domains with tracking categories get appropriate scores
            enhanced_fingerprinting = max(base_fingerprinting, category_tracking_score)
            
            # Reduce num_resources importance by 50% through feature scaling
            raw_num_resources = len(data.get('resources', []))
            scaled_num_resources = raw_num_resources * 0.5  # Reduce importance by 50%
            
            # Extract basic features
            features = {
                'domain': domain_name,
                'fingerprinting': enhanced_fingerprinting,
                'cookies_prevalence': data.get('cookies', 0.0),
                'global_prevalence': data.get('prevalence', 0.0),
                'num_sites': data.get('sites', 0),
                'num_subdomains': len(data.get('subdomains', [])),
                'num_cnames': len(data.get('cnames', [])),
                'num_resources': scaled_num_resources,
                'num_top_initiators': len(data.get('topInitiators', [])),
                'owner_present': 1 if data.get('owner') else 0,
            }
            
            # Extract resource type counts
            types_dict = data.get('types', {})
            resource_types = ['Script', 'XHR', 'Image', 'CSS', 'Font', 'Media']
            for res_type in resource_types:
                features[f'resource_type_{res_type.lower()}_count'] = types_dict.get(res_type, 0)
            
            # Calculate average resource fingerprinting
            resources = data.get('resources', [])
            if resources:
                fingerprinting_scores = [r.get('fingerprinting', 0) for r in resources]
                features['avg_resource_fingerprinting'] = np.mean(fingerprinting_scores)
                
                # Check if any resource has example sites
                has_example_sites = any(r.get('exampleSites') for r in resources)
                features['has_example_sites'] = 1 if has_example_sites else 0
            else:
                features['avg_resource_fingerprinting'] = 0.0
                features['has_example_sites'] = 0
            
            return features
            
        except Exception as e:
            print(f"Error parsing {json_path}: {e}")
            return None
    
    def extract_all_features(self) -> pd.DataFrame:
        """Extract features from all domain JSON files"""
        if not self.domains_path.exists():
            raise FileNotFoundError(f"Domains path not found: {self.domains_path}")
        
        # Check if domains are organized by country directories
        country_dirs = [d for d in self.domains_path.iterdir() if d.is_dir()]
        
        features_list = []
        
        if country_dirs:
            # New structure with country directories - process ALL countries and ALL domains
            print(f"Found {len(country_dirs)} country directories")
            total_files = 0
            
            for country_dir in country_dirs:  # Process ALL countries, not just first 3
                print(f"Processing {country_dir.name}...")
                json_files = list(country_dir.glob("*.json"))
                total_files += len(json_files)
                print(f"  Found {len(json_files)} domain files")
                
                # Process ALL files, not just first 500
                for i, json_file in enumerate(json_files):
                    if i % 1000 == 0 and i > 0:  # Progress every 1000 files
                        print(f"    Processed {i}/{len(json_files)} files")
                    
                    features = self.parse_domain_json(json_file)
                    if features:
                        features_list.append(features)
                        
            print(f"✅ Processed {total_files} total files across all countries")
        else:
            # Old structure with files directly in domains/
            json_files = list(self.domains_path.glob("*.json"))
            print(f"Found {len(json_files)} domain JSON files")
            
            for i, json_file in enumerate(json_files):
                if i % 1000 == 0 and i > 0:
                    print(f"  Processed {i}/{len(json_files)} files")
                    
                features = self.parse_domain_json(json_file)
                if features:
                    features_list.append(features)
        
        print(f"Successfully parsed {len(features_list)} domains")
        return pd.DataFrame(features_list)

class TargetConstructor:
    """Construct tracking intensity target variable"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
    
    def compute_tracking_intensity(self) -> pd.Series:
        """
        Compute tracking intensity score from domain features
        Higher score = more invasive tracking
        """
        # Get max sites for normalization
        max_sites = self.df['num_sites'].max() if self.df['num_sites'].max() > 0 else 1
        
        # Compute raw intensity score
        intensity_raw = (
            self.df['fingerprinting'] * 2.5 +
            self.df['cookies_prevalence'] * 100 +
            self.df['global_prevalence'] * 100 +
            self.df['num_resources'] * 0.8 +
            (self.df['num_sites'] / max_sites) * 1.5 +
            self.df['avg_resource_fingerprinting'] * 1.5
        )
        
        # Normalize to 0-1 using robust scaling to handle outliers
        scaler = RobustScaler()
        intensity_normalized = scaler.fit_transform(intensity_raw.values.reshape(-1, 1)).flatten()
        
        # Ensure values are in [0, 1] range
        intensity_normalized = np.clip(intensity_normalized, 0, 1)
        
        return pd.Series(intensity_normalized, index=self.df.index)

class DomainRiskModel:
    """Gradient boosted tree regressor for domain risk prediction"""
    
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_type = None
        
    def _create_model(self):
        """Create the best available gradient boosting model"""
        if HAS_LIGHTGBM:
            try:
                self.model_type = "lightgbm"
                return lgb.LGBMRegressor(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=self.random_state,
                    verbosity=-1
                )
            except Exception as e:
                print(f"⚠️  LightGBM failed at runtime: {e}")
                print("   Falling back to scikit-learn")
                pass  # Fall through to next option
                
        if HAS_XGBOOST:
            try:
                self.model_type = "xgboost"
                return xgb.XGBRegressor(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=self.random_state,
                    verbosity=0
                )
            except Exception as e:
                print(f"⚠️  XGBoost failed at runtime: {e}")
                print("   Falling back to scikit-learn")
                pass  # Fall through to sklearn
                
        # Default fallback to scikit-learn
        self.model_type = "sklearn"
        print("📦 Using scikit-learn HistGradientBoostingRegressor")
        return HistGradientBoostingRegressor(
            max_iter=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=self.random_state
        )
    
    def train(self, X: pd.DataFrame, y: pd.Series) -> Tuple[Dict, pd.DataFrame]:
        """Train the model and return evaluation metrics"""
        # Store feature names
        self.feature_names = list(X.columns)
        
        # Split data domain-wise
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=self.random_state
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Create and train model
        self.model = self._create_model()
        self.model.fit(X_train_scaled, y_train)
        
        # Make predictions
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_test = self.model.predict(X_test_scaled)
        
        # Calculate metrics
        metrics = {
            'train_mae': mean_absolute_error(y_train, y_pred_train),
            'test_mae': mean_absolute_error(y_test, y_pred_test),
            'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
            'train_spearman': spearmanr(y_train, y_pred_train)[0],
            'test_spearman': spearmanr(y_test, y_pred_test)[0],
            'model_type': self.model_type
        }
        
        # Get feature importance
        if hasattr(self.model, 'feature_importances_'):
            importance_df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
        else:
            importance_df = pd.DataFrame()
        
        return metrics, importance_df
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict tracking intensity for new domains"""
        if self.model is None or self.scaler is None:
            raise ValueError("Model must be trained first")
        
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)
    
    def save_model(self, model_path: str, features_csv_path: str, features_json_path: str, 
                  domain_features_df: pd.DataFrame):
        """Save trained model and feature mappings"""
        # Save model
        model_artifacts = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_type': self.model_type
        }
        joblib.dump(model_artifacts, model_path)
        
        # Save domain features as CSV
        domain_features_df.to_csv(features_csv_path, index=False)
        
        # Save domain features as JSON for fast lookup
        features_dict = {}
        for _, row in domain_features_df.iterrows():
            domain = row['domain']
            features = row.drop('domain').to_dict()
            features_dict[domain] = features
        
        with open(features_json_path, 'w') as f:
            json.dump(features_dict, f, indent=2)
        
        print(f"Model saved to: {model_path}")
        print(f"Features CSV saved to: {features_csv_path}")
        print(f"Features JSON saved to: {features_json_path}")

def main():
    parser = argparse.ArgumentParser(description='Train domain risk model from TrackerRadar data')
    parser.add_argument('--tracker-radar-path', default='./data/tracker-radar',
                       help='Path to TrackerRadar repository')
    parser.add_argument('--out-model-path', default='./models/domain_risk_model.pkl',
                       help='Output path for trained model')
    parser.add_argument('--clone', action='store_true',
                       help='Clone TrackerRadar repository if it doesn\'t exist')
    
    args = parser.parse_args()
    
    # Create output directories
    model_dir = Path(args.out_model_path).parent
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize parser
    parser_obj = TrackerRadarParser(args.tracker_radar_path)
    
    # Clone repository if requested
    if args.clone:
        if not parser_obj.clone_tracker_radar(args.tracker_radar_path):
            sys.exit(1)
    
    # Extract features
    print("Extracting domain features...")
    try:
        df = parser_obj.extract_all_features()
        print(f"Extracted features for {len(df)} domains")
    except Exception as e:
        print(f"Error extracting features: {e}")
        sys.exit(1)
    
    # Construct target variable
    print("Computing tracking intensity targets...")
    target_constructor = TargetConstructor(df)
    tracking_intensity = target_constructor.compute_tracking_intensity()
    
    # Prepare training data
    feature_cols = [col for col in df.columns if col != 'domain']
    X = df[feature_cols]
    y = tracking_intensity
    
    print(f"Training data shape: {X.shape}")
    print(f"Feature columns: {feature_cols}")
    
    # Train model
    print("Training domain risk model...")
    model = DomainRiskModel()
    metrics, importance_df = model.train(X, y)
    
    # Print results
    print("\nModel Training Results:")
    print(f"Model type: {metrics['model_type']}")
    print(f"Test MAE: {metrics['test_mae']:.4f}")
    print(f"Test RMSE: {metrics['test_rmse']:.4f}")
    print(f"Test Spearman correlation: {metrics['test_spearman']:.4f}")
    
    if not importance_df.empty:
        print("\nTop 10 Feature Importances:")
        print(importance_df.head(10))
    
    # Save model and artifacts
    features_csv_path = model_dir / "domain_features.csv"
    features_json_path = model_dir / "domain_features.json"
    
    model.save_model(
        args.out_model_path,
        str(features_csv_path),
        str(features_json_path),
        df
    )
    
    print(f"\nModel training complete! Files saved to {model_dir}")

if __name__ == "__main__":
    main()