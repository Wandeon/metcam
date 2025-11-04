"""
Calibration Service for Panorama Stitching

Performs one-time camera calibration to calculate homography transformation.
Uses VPI for GPU-accelerated feature detection.
"""

import vpi
import numpy as np
import cv2
import logging
from typing import List, Tuple, Dict, Optional
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class CalibrationService:
    """Handles camera calibration for panorama stitching"""

    def __init__(self, config_manager):
        """
        Initialize calibration service

        Args:
            config_manager: PanoramaConfigManager instance
        """
        self.config_manager = config_manager
        self.calibration_frames = []
        self.min_frames = 10
        self.target_frames = 15
        self.is_calibrating = False

        logger.info("CalibrationService initialized")

    def start(self) -> bool:
        """
        Start calibration mode

        Returns:
            True if calibration started successfully
        """
        try:
            # Clear any existing calibration data
            self.calibration_frames = []
            self.is_calibrating = True

            logger.info("Calibration mode started")
            return True

        except Exception as e:
            logger.error(f"Error starting calibration: {e}", exc_info=True)
            self.is_calibrating = False
            return False

    def capture_frame_pair(
        self,
        frame_cam0: np.ndarray,
        frame_cam1: np.ndarray,
        timestamp: float
    ) -> bool:
        """
        Alias for capture_calibration_frame for backward compatibility
        """
        return self.capture_calibration_frame(frame_cam0, frame_cam1, timestamp)

    def capture_calibration_frame(
        self,
        frame_cam0: np.ndarray,
        frame_cam1: np.ndarray,
        timestamp: float
    ) -> bool:
        """
        Capture a synchronized frame pair for calibration

        Args:
            frame_cam0: Frame from camera 0
            frame_cam1: Frame from camera 1
            timestamp: Capture timestamp

        Returns:
            True if frame was captured successfully
        """
        try:
            # Validate frames
            if frame_cam0 is None or frame_cam1 is None:
                logger.error("Invalid frames: one or both frames are None")
                return False

            if frame_cam0.size == 0 or frame_cam1.size == 0:
                logger.error("Invalid frames: one or both frames are empty")
                return False

            # Check frame quality (basic sharpness check)
            quality_cam0 = self._check_frame_quality(frame_cam0)
            quality_cam1 = self._check_frame_quality(frame_cam1)

            if quality_cam0 < 10.0 or quality_cam1 < 10.0:
                logger.warning(
                    f"Low quality frames: cam0={quality_cam0:.2f}, cam1={quality_cam1:.2f}"
                )
                # Still allow capture but warn

            # Store frame pair
            self.calibration_frames.append({
                'frame_cam0': frame_cam0.copy(),
                'frame_cam1': frame_cam1.copy(),
                'timestamp': timestamp,
                'quality_cam0': quality_cam0,
                'quality_cam1': quality_cam1
            })

            logger.info(
                f"Captured calibration frame {len(self.calibration_frames)}/{self.target_frames} "
                f"(quality: cam0={quality_cam0:.2f}, cam1={quality_cam1:.2f})"
            )

            return True

        except Exception as e:
            logger.error(f"Error capturing calibration frame: {e}", exc_info=True)
            return False

    def _check_frame_quality(self, frame: np.ndarray) -> float:
        """
        Check frame quality using Laplacian variance (sharpness)

        Args:
            frame: Input frame (BGR or grayscale)

        Returns:
            Quality score (higher is better)
        """
        try:
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Calculate Laplacian variance (measure of sharpness)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = laplacian.var()

            return variance

        except Exception as e:
            logger.error(f"Error checking frame quality: {e}")
            return 0.0

    def get_calibration_progress(self) -> Dict:
        """Get calibration progress information"""
        frames_captured = len(self.calibration_frames)

        return {
            'is_calibrating': self.is_calibrating,
            'frames_captured': frames_captured,
            'frames_needed': self.min_frames,
            'frames_target': self.target_frames,
            'ready_to_calculate': frames_captured >= self.min_frames,
            'progress_percent': int((frames_captured / self.target_frames) * 100)
        }

    def calculate_homography(self) -> Tuple[bool, Optional[np.ndarray], Dict]:
        """
        Calculate homography matrix from captured frames

        Returns:
            Tuple of (success, homography_matrix, metadata)
        """
        try:
            if len(self.calibration_frames) < self.min_frames:
                logger.error(
                    f"Insufficient frames for calibration: {len(self.calibration_frames)}/{self.min_frames}"
                )
                return False, None, {
                    'error': f'Need at least {self.min_frames} frames, got {len(self.calibration_frames)}'
                }

            logger.info(f"Starting homography calculation with {len(self.calibration_frames)} frames")

            # Extract features from all frames
            all_keypoints_cam0 = []
            all_keypoints_cam1 = []

            for i, frame_data in enumerate(self.calibration_frames):
                logger.debug(f"Processing frame {i+1}/{len(self.calibration_frames)}")

                kp0 = self._extract_features_vpi(frame_data['frame_cam0'])
                kp1 = self._extract_features_vpi(frame_data['frame_cam1'])

                if len(kp0) > 0 and len(kp1) > 0:
                    all_keypoints_cam0.append(kp0)
                    all_keypoints_cam1.append(kp1)
                else:
                    logger.warning(f"Frame {i} has insufficient features")

            if len(all_keypoints_cam0) < self.min_frames:
                logger.error("Too few frames with valid features")
                return False, None, {'error': 'Insufficient features in captured frames'}

            logger.info(f"Feature extraction complete: {len(all_keypoints_cam0)} valid frames")

            # Match features across all frame pairs
            all_matches = []
            for kp0, kp1 in zip(all_keypoints_cam0, all_keypoints_cam1):
                matches = self._match_features(kp0, kp1)
                if len(matches) > 0:
                    all_matches.append(matches)

            if len(all_matches) == 0:
                logger.error("No feature matches found")
                return False, None, {'error': 'No matching features found between cameras'}

            # Combine all matches
            combined_points_cam0 = []
            combined_points_cam1 = []

            for matches in all_matches:
                combined_points_cam0.extend(matches[:, 0, :])
                combined_points_cam1.extend(matches[:, 1, :])

            points_cam0 = np.array(combined_points_cam0)
            points_cam1 = np.array(combined_points_cam1)

            logger.info(f"Total matched points: {len(points_cam0)}")

            # Calculate homography using RANSAC
            H, inlier_ratio = self._calculate_homography_ransac(points_cam0, points_cam1)

            if H is None:
                logger.error("Homography calculation failed")
                return False, None, {'error': 'RANSAC homography calculation failed'}

            # Validate homography quality
            is_valid, quality_score = self._validate_homography(H, points_cam0, points_cam1)

            if not is_valid:
                logger.warning(f"Homography validation failed (quality={quality_score:.3f})")
                return False, None, {
                    'error': 'Homography quality too low',
                    'quality_score': quality_score
                }

            # Calculate reprojection error
            reprojection_error = self._calculate_reprojection_error(
                H, points_cam0, points_cam1
            )

            logger.info(
                f"Homography calculated successfully: "
                f"quality={quality_score:.3f}, "
                f"inliers={inlier_ratio:.2%}, "
                f"error={reprojection_error:.2f}px"
            )

            # Prepare metadata
            metadata = {
                'calibration_date': datetime.now().isoformat(),
                'quality_score': float(quality_score),
                'inlier_ratio': float(inlier_ratio),
                'reprojection_error': float(reprojection_error),
                'num_frames': len(self.calibration_frames),
                'num_matches': len(points_cam0),
                'homography_matrix': H.tolist()
            }

            # Save calibration data
            self.config_manager.save_calibration(metadata)

            # Exit calibration mode after successful calculation
            self.is_calibrating = False

            return True, H, metadata

        except Exception as e:
            logger.error(f"Error calculating homography: {e}", exc_info=True)
            self.is_calibrating = False
            return False, None, {'error': str(e)}

    def _extract_features_vpi(self, image: np.ndarray) -> np.ndarray:
        """
        Extract Harris corners using VPI CUDA backend

        Args:
            image: Input image (BGR or grayscale)

        Returns:
            Array of keypoints shape (N, 2) with [x, y] coordinates
        """
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # Use VPI for Harris corner detection
            with vpi.Backend.CUDA:
                # Create VPI image from numpy array
                vpi_image = vpi.asimage(gray, format=vpi.Format.U8)

                # Run Harris corner detection
                corners, scores = vpi_image.harriscorners(
                    backend=vpi.Backend.CUDA,
                    strength=20.0,
                    sensitivity=0.01,
                    min_nms_distance=8.0
                )

                # Convert to numpy array
                keypoints = corners.cpu()

            logger.debug(f"Extracted {len(keypoints)} Harris corners with VPI")

            return keypoints

        except Exception as e:
            logger.warning(f"VPI feature extraction failed, falling back to OpenCV: {e}")

            # Fallback to OpenCV Harris corners
            try:
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image

                # Harris corner detection with OpenCV
                gray_float = np.float32(gray)
                harris = cv2.cornerHarris(gray_float, 2, 3, 0.04)

                # Threshold and get coordinates
                harris = cv2.dilate(harris, None)
                threshold = 0.01 * harris.max()
                keypoints = np.argwhere(harris > threshold)

                # Convert from (row, col) to (x, y)
                keypoints = keypoints[:, [1, 0]].astype(np.float32)

                logger.debug(f"Extracted {len(keypoints)} Harris corners with OpenCV")

                return keypoints

            except Exception as e2:
                logger.error(f"OpenCV feature extraction also failed: {e2}")
                return np.array([])

    def _match_features(
        self,
        keypoints0: np.ndarray,
        keypoints1: np.ndarray
    ) -> np.ndarray:
        """
        Match features between two images using spatial proximity

        Args:
            keypoints0: Keypoints from camera 0, shape (N, 2)
            keypoints1: Keypoints from camera 1, shape (M, 2)

        Returns:
            Matched points array, shape (K, 2, 2) where [:, 0, :] is cam0 and [:, 1, :] is cam1
        """
        if len(keypoints0) == 0 or len(keypoints1) == 0:
            return np.array([])

        try:
            # Simple nearest neighbor matching
            # For each point in cam0, find closest point in cam1
            matches = []
            max_distance = 50.0  # Maximum pixel distance for a match

            for kp0 in keypoints0:
                # Calculate distances to all points in cam1
                distances = np.sqrt(np.sum((keypoints1 - kp0) ** 2, axis=1))

                # Find closest point
                min_idx = np.argmin(distances)
                min_dist = distances[min_idx]

                # Accept match if within threshold
                if min_dist < max_distance:
                    matches.append([kp0, keypoints1[min_idx]])

            if len(matches) > 0:
                matches = np.array(matches)
                logger.debug(f"Matched {len(matches)} features")
                return matches
            else:
                return np.array([])

        except Exception as e:
            logger.error(f"Error matching features: {e}")
            return np.array([])

    def _calculate_homography_ransac(
        self,
        points0: np.ndarray,
        points1: np.ndarray
    ) -> Tuple[Optional[np.ndarray], float]:
        """
        Calculate homography using RANSAC

        Args:
            points0: Points from camera 0, shape (N, 2)
            points1: Points from camera 1, shape (N, 2)

        Returns:
            Tuple of (homography_matrix, inlier_ratio)
        """
        try:
            if len(points0) < 4:
                logger.error(f"Insufficient points for homography: {len(points0)}")
                return None, 0.0

            # Use OpenCV's findHomography with RANSAC
            H, mask = cv2.findHomography(
                points1,  # Source points (cam1)
                points0,  # Destination points (cam0)
                cv2.RANSAC,
                ransacReprojThreshold=5.0,
                maxIters=2000,
                confidence=0.995
            )

            if H is None:
                logger.error("findHomography returned None")
                return None, 0.0

            # Calculate inlier ratio
            inlier_count = np.sum(mask)
            inlier_ratio = inlier_count / len(mask)

            logger.info(
                f"RANSAC homography: {inlier_count}/{len(mask)} inliers "
                f"({inlier_ratio:.2%})"
            )

            return H, inlier_ratio

        except Exception as e:
            logger.error(f"Error in RANSAC homography calculation: {e}", exc_info=True)
            return None, 0.0

    def _validate_homography(
        self,
        H: np.ndarray,
        points0: np.ndarray,
        points1: np.ndarray
    ) -> Tuple[bool, float]:
        """
        Validate homography quality

        Args:
            H: Homography matrix
            points0: Points from camera 0
            points1: Points from camera 1

        Returns:
            Tuple of (is_valid, quality_score)
            quality_score ranges from 0.0 to 1.0
        """
        try:
            # Check matrix condition number
            cond = np.linalg.cond(H)
            if cond > 1e6:
                logger.warning(f"Homography poorly conditioned: {cond:.2e}")
                return False, 0.0

            # Check determinant (should be non-zero and not too large/small)
            det = np.linalg.det(H)
            if abs(det) < 1e-6 or abs(det) > 1e6:
                logger.warning(f"Homography determinant out of range: {det:.2e}")
                return False, 0.0

            # Calculate reprojection error
            error = self._calculate_reprojection_error(H, points0, points1)

            # Quality score based on reprojection error
            # Excellent: < 2 pixels -> 1.0
            # Good: 2-5 pixels -> 0.8-1.0
            # Fair: 5-10 pixels -> 0.6-0.8
            # Poor: > 10 pixels -> < 0.6

            if error < 2.0:
                quality = 1.0
            elif error < 5.0:
                quality = 0.8 + (5.0 - error) / 3.0 * 0.2
            elif error < 10.0:
                quality = 0.6 + (10.0 - error) / 5.0 * 0.2
            else:
                quality = max(0.0, 0.6 - (error - 10.0) / 20.0)

            is_valid = quality >= 0.7  # Minimum acceptable quality

            logger.info(
                f"Homography validation: error={error:.2f}px, "
                f"quality={quality:.3f}, valid={is_valid}"
            )

            return is_valid, quality

        except Exception as e:
            logger.error(f"Error validating homography: {e}", exc_info=True)
            return False, 0.0

    def _calculate_reprojection_error(
        self,
        H: np.ndarray,
        points0: np.ndarray,
        points1: np.ndarray
    ) -> float:
        """
        Calculate average reprojection error

        Args:
            H: Homography matrix (3x3)
            points0: Destination points, shape (N, 2)
            points1: Source points, shape (N, 2)

        Returns:
            Average reprojection error in pixels
        """
        try:
            # Transform points1 using homography
            points1_h = np.concatenate([points1, np.ones((len(points1), 1))], axis=1)
            transformed = (H @ points1_h.T).T

            # Convert from homogeneous coordinates
            transformed = transformed[:, :2] / transformed[:, 2:3]

            # Calculate distances
            errors = np.sqrt(np.sum((transformed - points0) ** 2, axis=1))

            # Return mean error
            return float(np.mean(errors))

        except Exception as e:
            logger.error(f"Error calculating reprojection error: {e}")
            return float('inf')

    def reset(self) -> None:
        """Clear captured calibration frames and exit calibration mode"""
        self.calibration_frames = []
        self.is_calibrating = False
        logger.info("Calibration frames cleared and calibration mode stopped")
