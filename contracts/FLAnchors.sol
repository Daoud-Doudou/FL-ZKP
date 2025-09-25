// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FLAnchors {
    struct RoundAnchor {
        bytes32 H_model;     // keccak256 du modèle agrégé quantifié
        bytes32 H_artifacts; // keccak256(concat proofs/public)
        bool exists;
    }

    mapping(uint256 => RoundAnchor) public anchors;
    event RoundAnchored(uint256 indexed roundId, bytes32 H_model, bytes32 H_artifacts);

    function anchorRound(
        uint256 roundId,
        bytes32 H_model,
        bytes32 H_artifacts
    ) external {
        require(!anchors[roundId].exists, "round already anchored");
        anchors[roundId] = RoundAnchor({ H_model: H_model, H_artifacts: H_artifacts, exists: true });
        emit RoundAnchored(roundId, H_model, H_artifacts);
    }
}
