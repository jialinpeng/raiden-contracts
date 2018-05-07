from raiden_contracts.utils.config import (
    C_TOKEN_NETWORK_REGISTRY,
    C_TOKEN_NETWORK,
    C_SECRET_REGISTRY
)
from .utils import get_pending_transfers_tree, get_locked_amount
from raiden_contracts.utils.merkle import get_merkle_root


def test_token_network_registry(
        chain,
        web3,
        owner,
        token_network_registry,
        custom_token,
        secret_registry,
        print_gas
):
    web3.testing.mine(3)

    TokenNetworkRegistry = chain.provider.get_contract_factory(C_TOKEN_NETWORK_REGISTRY)
    deploy_txn_hash = TokenNetworkRegistry.deploy(
        transaction={'from': owner},
        args=[secret_registry.address, int(chain.web3.version.network)]
    )
    print_gas(deploy_txn_hash, C_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')

    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)
    print_gas(txn_hash, C_TOKEN_NETWORK_REGISTRY + '.createERC20TokenNetwork')


def test_token_network_deployment(
        chain,
        print_gas,
        custom_token,
        secret_registry,
        token_network_registry
):
    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    deploy_txn_hash = TokenNetwork.deploy(args=[
        custom_token.address,
        secret_registry.address,
        int(chain.web3.version.network)
    ])

    print_gas(deploy_txn_hash, C_TOKEN_NETWORK + ' DEPLOYMENT')


def test_token_network_create(
        chain,
        print_gas,
        custom_token,
        secret_registry,
        token_network_registry
):
    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)

    print_gas(txn_hash, C_TOKEN_NETWORK_REGISTRY + ' createERC20TokenNetwork')


def test_secret_registry(secret_registry, print_gas):
    secret = b'secretsecretsecretsecretsecretse'
    txn_hash = secret_registry.transact().registerSecret(secret)
    print_gas(txn_hash, C_SECRET_REGISTRY + '.registerSecret')


def test_channel_cycle(
        web3,
        token_network,
        create_channel,
        channel_deposit,
        secret_registry,
        get_accounts,
        print_gas,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B) = get_accounts(2)
    settle_timeout = 11

    (channel_identifier, txn_hash) = create_channel(A, B, settle_timeout)
    print_gas(txn_hash, C_TOKEN_NETWORK + '.openChannel')

    txn_hash = channel_deposit(A, 20, B)
    txn_hash = channel_deposit(B, 10, A)
    print_gas(txn_hash, C_TOKEN_NETWORK + '.setDeposit')

    pending_transfers_tree1 = get_pending_transfers_tree(web3, [1, 1, 2, 3], [2, 1])
    locksroot1 = get_merkle_root(pending_transfers_tree1.merkle_tree)
    locked_amount1 = get_locked_amount(pending_transfers_tree1.transfers)

    pending_transfers_tree2 = get_pending_transfers_tree(web3, [3], [], 7)
    locksroot2 = get_merkle_root(pending_transfers_tree2.merkle_tree)
    locked_amount2 = get_locked_amount(pending_transfers_tree2.transfers)

    balance_proof_A = create_balance_proof(
        channel_identifier,
        A,
        10,
        locked_amount1,
        5,
        locksroot1
    )
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        5,
        locked_amount2,
        3,
        locksroot2
    )
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    for lock in pending_transfers_tree1.unlockable:
        txn_hash = secret_registry.transact({'from': A}).registerSecret(lock[3])
    for lock in pending_transfers_tree2.unlockable:
        txn_hash = secret_registry.transact({'from': A}).registerSecret(lock[3])

    print_gas(txn_hash, C_SECRET_REGISTRY + '.registerSecret')

    txn_hash = token_network.transact({'from': A}).closeChannel(B, *balance_proof_B)
    print_gas(txn_hash, C_TOKEN_NETWORK + '.closeChannel')

    txn_hash = token_network.transact({'from': B}).updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B
    )
    print_gas(txn_hash, C_TOKEN_NETWORK + '.updateNonClosingBalanceProof')

    web3.testing.mine(settle_timeout)
    txn_hash = token_network.transact().settleChannel(
        A, 10, locked_amount1, locksroot1,
        B, 5, locked_amount2, locksroot2
    )
    print_gas(txn_hash, C_TOKEN_NETWORK + '.settleChannel')

    txn_hash = token_network.transact().unlock(
        A,
        B,
        pending_transfers_tree2.packed_transfers
    )
    print_gas(txn_hash, '{0}.unlock {1} locks'.format(
        C_TOKEN_NETWORK,
        len(pending_transfers_tree2.transfers)
    ))

    txn_hash = token_network.transact().unlock(
        B,
        A,
        pending_transfers_tree1.packed_transfers
    )
    print_gas(txn_hash, '{0}.unlock {1} locks'.format(
        C_TOKEN_NETWORK,
        len(pending_transfers_tree1.transfers)
    ))
